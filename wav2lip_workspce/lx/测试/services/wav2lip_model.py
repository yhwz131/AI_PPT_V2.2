"""
Wav2Lip 模型预加载服务
- Wav2Lip 模型启动时加载，后续推理直接复用
- 人脸检测器启动时加载，避免每次重建
- 同一人脸视频的帧数据和检测结果缓存，多次请求只读取/检测一次
"""
import os
import sys
import hashlib
import cv2
import numpy as np
import subprocess
import threading
import torch

_model = None
_device = None
_face_detector = None
_lock = threading.Lock()

def _sharpen_face(face_img, strength=0.4):
    """轻量级 unsharp-mask 锐化，提升 Wav2Lip 96x96 上采样后的面部清晰度"""
    blurred = cv2.GaussianBlur(face_img, (0, 0), 3)
    return cv2.addWeighted(face_img, 1.0 + strength, blurred, -strength, 0)

WAV2LIP_DIR = None
CHECKPOINT_PATH = None

_video_cache = {}
_video_cache_lock = threading.Lock()
_MAX_CACHE_ENTRIES = 3


def init(wav2lip_dir: str, checkpoint_path: str):
    global WAV2LIP_DIR, CHECKPOINT_PATH
    WAV2LIP_DIR = wav2lip_dir
    CHECKPOINT_PATH = checkpoint_path
    if wav2lip_dir not in sys.path:
        sys.path.insert(0, wav2lip_dir)


def load():
    """预加载 Wav2Lip 模型和人脸检测器到 GPU（仅执行一次）"""
    global _model, _device, _face_detector
    if _model is not None:
        return

    _device = 'cuda' if torch.cuda.is_available() else 'cpu'

    print(f"[Wav2Lip] Loading model from {CHECKPOINT_PATH} to {_device} ...")
    _model = torch.jit.load(CHECKPOINT_PATH, map_location=_device)
    _model.eval()
    print(f"[Wav2Lip] Model loaded on {_device}")

    print("[Wav2Lip] Loading face detector ...")
    import face_detection as fd
    _face_detector = fd.FaceAlignment(fd.LandmarksType._2D, flip_input=False, device=_device)
    print("[Wav2Lip] Face detector loaded")


def _get_video_hash(path: str) -> str:
    stat = os.stat(path)
    key = f"{path}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.md5(key.encode()).hexdigest()


def _read_video_cached(face_video_path: str):
    """读取视频帧，对同一文件使用缓存"""
    vhash = _get_video_hash(face_video_path)

    with _video_cache_lock:
        if vhash in _video_cache:
            entry = _video_cache[vhash]
            return entry['frames'], entry['fps'], entry['face_det']

    if face_video_path.split('.')[-1].lower() in ['jpg', 'png', 'jpeg']:
        frames = [cv2.imread(face_video_path)]
        fps = 25.0
    else:
        cap = cv2.VideoCapture(face_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = []
        while True:
            ok, frame = cap.read()
            if not ok:
                cap.release()
                break
            frames.append(frame)

    if not frames:
        return [], 0, []

    pads = [0, 10, 0, 0]
    face_det = _face_detect_cached(frames, pads)

    with _video_cache_lock:
        if len(_video_cache) >= _MAX_CACHE_ENTRIES:
            oldest = next(iter(_video_cache))
            del _video_cache[oldest]
        _video_cache[vhash] = {
            'frames': frames,
            'fps': fps,
            'face_det': face_det,
        }

    return frames, fps, face_det


def _face_detect_cached(images, pads, batch_size=16):
    """使用预加载的检测器进行人脸检测"""
    detector = _face_detector
    if detector is None:
        import face_detection as fd
        detector = fd.FaceAlignment(fd.LandmarksType._2D, flip_input=False, device=_device)

    bs = batch_size
    while True:
        predictions = []
        try:
            for i in range(0, len(images), bs):
                predictions.extend(
                    detector.get_detections_for_batch(np.array(images[i:i + bs]))
                )
        except RuntimeError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if bs == 1:
                raise
            bs //= 2
            continue
        break

    pady1, pady2, padx1, padx2 = pads
    results = []
    for rect, image in zip(predictions, images):
        if rect is None:
            raise ValueError('Face not detected in frame')
        y1 = max(0, rect[1] - pady1)
        y2 = min(image.shape[0], rect[3] + pady2)
        x1 = max(0, rect[0] - padx1)
        x2 = min(image.shape[1], rect[2] + padx2)
        results.append([x1, y1, x2, y2])

    boxes = np.array(results)
    T = 5
    for i in range(len(boxes)):
        start = max(0, i - T + 1)
        window = boxes[start:i + 1]
        boxes[i] = np.mean(window, axis=0)

    return [
        [image[y1:y2, x1:x2], (y1, y2, x1, x2)]
        for image, (x1, y1, x2, y2) in zip(images, boxes)
    ]


def infer(face_video_path: str, audio_path: str, output_path: str) -> bool:
    """使用预加载的模型执行 Wav2Lip 推理（含缓存优化）"""
    if _model is None:
        raise RuntimeError("Wav2Lip model not loaded. Call load() first.")

    _ensure_wav2lip_on_path()

    try:
        import audio as wav2lip_audio

        img_size = 96
        mel_step_size = 16
        wav2lip_batch_size = 128

        full_frames, fps, face_det_all = _read_video_cached(face_video_path)
        if not full_frames:
            print("[Wav2Lip] No frames read from video")
            return False

        tmp_wav = None
        audio_for_mel = audio_path
        if not audio_path.endswith('.wav'):
            tmp_wav = os.path.join(os.path.dirname(output_path) or '.', '_temp_audio.wav')
            subprocess.call(
                f'ffmpeg -y -i "{audio_path}" -strict -2 "{tmp_wav}"',
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            audio_for_mel = tmp_wav

        wav = wav2lip_audio.load_wav(audio_for_mel, 16000)
        mel = wav2lip_audio.melspectrogram(wav)

        if np.isnan(mel.reshape(-1)).sum() > 0:
            print("[Wav2Lip] Mel contains NaN")
            return False

        mel_chunks = []
        mel_idx_multiplier = 80.0 / fps
        i = 0
        while True:
            start_idx = int(i * mel_idx_multiplier)
            if start_idx + mel_step_size > len(mel[0]):
                mel_chunks.append(mel[:, len(mel[0]) - mel_step_size:])
                break
            mel_chunks.append(mel[:, start_idx:start_idx + mel_step_size])
            i += 1

        n_frames = min(len(full_frames), len(mel_chunks))
        frames_slice = full_frames[:n_frames]
        face_det_slice = face_det_all[:n_frames]

        temp_dir_abs = os.path.join(WAV2LIP_DIR, 'temp')
        os.makedirs(temp_dir_abs, exist_ok=True)
        temp_avi = os.path.join(temp_dir_abs, 'result.avi')

        frame_h, frame_w = frames_slice[0].shape[:-1]
        out = cv2.VideoWriter(
            temp_avi, cv2.VideoWriter_fourcc(*'DIVX'), fps, (frame_w, frame_h)
        )

        img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []

        for idx, m in enumerate(mel_chunks):
            frame_idx = idx % len(frames_slice)
            frame_to_save = frames_slice[frame_idx].copy()
            face, coords = face_det_slice[frame_idx]
            face_copy = face.copy()
            face_resized = cv2.resize(face_copy, (img_size, img_size))

            img_batch.append(face_resized)
            mel_batch.append(m)
            frame_batch.append(frame_to_save)
            coords_batch.append(coords)

            if len(img_batch) >= wav2lip_batch_size:
                _process_batch(img_batch, mel_batch, frame_batch, coords_batch, img_size, out)
                img_batch, mel_batch, frame_batch, coords_batch = [], [], [], []

        if img_batch:
            _process_batch(img_batch, mel_batch, frame_batch, coords_batch, img_size, out)

        out.release()

        cmd = f'ffmpeg -y -i "{audio_path}" -i "{temp_avi}" -strict -2 -q:v 1 "{output_path}"'
        subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if tmp_wav and os.path.exists(tmp_wav):
            os.remove(tmp_wav)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("[Wav2Lip] CUDA cache cleared after inference")

        return os.path.exists(output_path)

    except Exception as e:
        print(f"[Wav2Lip] Inference error: {e}")
        import traceback
        traceback.print_exc()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return False


def clear_video_cache():
    """清除视频帧缓存以释放内存"""
    with _video_cache_lock:
        _video_cache.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    import gc
    gc.collect()
    print("[Wav2Lip] Video cache cleared & CUDA cache released")


def _ensure_wav2lip_on_path():
    """确保 WAV2LIP_DIR 在 sys.path 中（线程安全，不改 cwd）"""
    if WAV2LIP_DIR and WAV2LIP_DIR not in sys.path:
        sys.path.insert(0, WAV2LIP_DIR)


def _process_batch(img_batch, mel_batch, frame_batch, coords_batch, img_size, out):
    """处理一个 batch 的推理"""
    img_batch_np = np.asarray(img_batch)
    mel_batch_np = np.asarray(mel_batch)

    img_masked = img_batch_np.copy()
    img_masked[:, img_size // 2:] = 0
    img_batch_np = np.concatenate((img_masked, img_batch_np), axis=3) / 255.0
    mel_batch_np = np.reshape(
        mel_batch_np, [len(mel_batch_np), mel_batch_np.shape[1], mel_batch_np.shape[2], 1]
    )

    img_t = torch.FloatTensor(np.transpose(img_batch_np, (0, 3, 1, 2))).to(_device)
    mel_t = torch.FloatTensor(np.transpose(mel_batch_np, (0, 3, 1, 2))).to(_device)

    with torch.no_grad():
        pred = _model(mel_t, img_t)

    pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0

    del img_t, mel_t

    for p, f, c in zip(pred, frame_batch, coords_batch):
        y1, y2, x1, x2 = c
        p = cv2.resize(p.astype(np.uint8), (x2 - x1, y2 - y1))

        p = _sharpen_face(p)

        h, w = y2 - y1, x2 - x1
        feather = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(feather, (w // 2, h // 2), (w // 2 - 4, h // 2 - 4),
                     0, 0, 360, 1.0, -1)
        feather = cv2.GaussianBlur(feather, (15, 15), 0)
        alpha = feather[..., np.newaxis]
        roi = f[y1:y2, x1:x2].astype(np.float32)
        f[y1:y2, x1:x2] = (alpha * p.astype(np.float32) + (1.0 - alpha) * roi).astype(np.uint8)

        out.write(f)

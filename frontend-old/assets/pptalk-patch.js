(function () {
  "use strict";

  window.__pptalk_style = "normal";
  window.__pptalk_welcome_text = "欢迎来到云南水利水电职业技术学院";
  window.__pptalk_bgm_mode = "default";
  window.__pptalk_bgm_path = "";
  window.__pptalk_emo_method = "0";
  window.__pptalk_emo_vec = "";
  window.__pptalk_emo_text = "";
  window.__pptalk_vec_valid = true;

  var VEC_MAX_EACH = 1.2;
  var VEC_MAX_SUM = 1.5;

  var BASE_URL = "";
  function getBaseURL() {
    if (BASE_URL) return BASE_URL;
    var el = document.querySelector("[id^=app]");
    if (el && el.__vue_app__) {
      var cfg = el.__vue_app__.config.globalProperties;
      if (cfg && cfg.$baseURL) BASE_URL = cfg.$baseURL;
    }
    return BASE_URL;
  }

  function injectCSS() {
    if (document.getElementById("pptalk-patch-css")) return;
    var style = document.createElement("style");
    style.id = "pptalk-patch-css";
    style.textContent =
      '.patch-section{background:#f8f9ff;border:1px solid #e0e4f0;border-radius:12px;padding:20px;margin-top:18px;}' +
      '.patch-section .patch-title{font-size:15px;font-weight:600;color:#333;margin-bottom:14px;display:flex;align-items:center;gap:6px;}' +
      '.patch-section .patch-title::before{content:"";width:4px;height:16px;background:linear-gradient(180deg,#6777ef,#a0b0ff);border-radius:2px;}' +
      '.patch-row{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;}' +
      '.patch-row:last-child{margin-bottom:0;}' +
      '.patch-label{font-size:13px;color:#555;min-width:80px;flex-shrink:0;}' +
      '.patch-radio-group{display:flex;gap:8px;flex-wrap:wrap;}' +
      '.patch-radio{display:flex;align-items:center;gap:4px;padding:6px 14px;border:1.5px solid #d0d5e0;border-radius:20px;cursor:pointer;font-size:13px;color:#555;transition:all .2s;user-select:none;background:#fff;}' +
      '.patch-radio:hover{border-color:#6777ef;color:#6777ef;}' +
      '.patch-radio.active{border-color:#6777ef;background:#6777ef;color:#fff;font-weight:500;}' +
      '.patch-input{flex:1;min-width:120px;padding:7px 12px;border:1.5px solid #d0d5e0;border-radius:8px;font-size:13px;outline:none;transition:border-color .2s;}' +
      '.patch-input:focus{border-color:#6777ef;}' +
      '.patch-textarea{width:100%;min-height:50px;padding:7px 12px;border:1.5px solid #d0d5e0;border-radius:8px;font-size:13px;outline:none;resize:vertical;transition:border-color .2s;font-family:inherit;}' +
      '.patch-textarea:focus{border-color:#6777ef;}' +
      '.patch-file-btn{display:inline-flex;align-items:center;gap:4px;padding:6px 16px;background:#6777ef;color:#fff;border:none;border-radius:8px;font-size:13px;cursor:pointer;transition:background .2s;}' +
      '.patch-file-btn:hover{background:#5566dd;}' +
      '.patch-file-name{font-size:12px;color:#888;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' +
      '.patch-hint{font-size:11px;color:#999;margin-top:4px;}' +
      '.patch-vec-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;width:100%;}' +
      '.patch-vec-item{display:flex;flex-direction:column;align-items:center;gap:2px;}' +
      '.patch-vec-item label{font-size:11px;color:#777;}' +
      '.patch-vec-item input{width:100%;padding:4px 6px;border:1px solid #d0d5e0;border-radius:6px;font-size:12px;text-align:center;outline:none;}' +
      '.patch-vec-item input:focus{border-color:#6777ef;}' +
      '.patch-vec-item input.vec-error{border-color:#f56c6c;background:#fff5f5;}' +
      '.patch-emo-extra{display:none;margin-top:8px;width:100%;}' +
      '.patch-emo-extra.visible{display:block;}' +
      '.patch-vec-status{font-size:11px;margin-top:6px;padding:4px 8px;border-radius:6px;display:inline-block;}' +
      '.patch-vec-status.ok{color:#67c23a;background:#f0f9eb;}' +
      '.patch-vec-status.warn{color:#e6a23c;background:#fdf6ec;}' +
      '.patch-vec-status.error{color:#f56c6c;background:#fef0f0;}' +
      '.step-item.clickable .step-num{cursor:pointer;position:relative;}' +
      '.step-item.clickable .step-num::after{content:"↩";position:absolute;top:-6px;right:-8px;font-size:9px;color:#6777ef;opacity:0;transition:opacity .2s;}' +
      '.step-item.clickable:hover .step-num{background-color:#eef0ff !important;color:#6777ef !important;box-shadow:0 1px 4px rgba(103,119,239,.25) !important;transform:scale(1.08);transition:all .2s;}' +
      '.step-item.clickable:hover .step-num::after{opacity:1;}' +
      '.step-item.clickable:hover .step-text{color:#6777ef !important;}';
    document.head.appendChild(style);
  }

  function createStyleSelector() {
    var wrap = document.createElement("div");
    wrap.className = "patch-section";
    wrap.id = "patch-style-section";
    var curStyle = window.__pptalk_style || "normal";
    var opts = [
      { val: "brief", label: "简略" },
      { val: "normal", label: "普通" },
      { val: "professional", label: "专业" }
    ];
    var radioHtml = opts.map(function (o) {
      return '<div class="patch-radio' + (o.val === curStyle ? ' active' : '') + '" data-val="' + o.val + '">' + o.label + '</div>';
    }).join("");
    wrap.innerHTML =
      '<div class="patch-title">文案风格</div>' +
      '<div class="patch-row">' +
      '<div class="patch-radio-group" id="patch-style-group">' + radioHtml +
      '</div></div>' +
      '<div class="patch-hint">简略: ~85字/页 | 普通: ~175字/页 | 专业: ~230字/页</div>';
    wrap.addEventListener("click", function (ev) {
      var t = ev.target.closest(".patch-radio");
      if (!t) return;
      wrap.querySelectorAll(".patch-radio").forEach(function (r) { r.classList.remove("active"); });
      t.classList.add("active");
      window.__pptalk_style = t.dataset.val;
    });
    return wrap;
  }

  function validateVecInputs(wrap) {
    var inputs = wrap.querySelectorAll("#patch-vec-grid input");
    var vec = [];
    var sum = 0;
    var hasError = false;
    inputs.forEach(function (inp) {
      var v = parseFloat(inp.value) || 0;
      if (v < 0) { v = 0; inp.value = "0"; }
      if (v > VEC_MAX_EACH) { v = VEC_MAX_EACH; inp.value = String(VEC_MAX_EACH); }
      vec.push(v);
      sum += v;
    });

    inputs.forEach(function (inp) { inp.classList.remove("vec-error"); });

    var statusEl = wrap.querySelector("#patch-vec-sum");
    if (sum > VEC_MAX_SUM) {
      hasError = true;
      statusEl.textContent = "向量之和 " + sum.toFixed(2) + " 超过上限 " + VEC_MAX_SUM + "，请降低某些维度（否则无法进入下一步）";
      statusEl.className = "patch-vec-status error";
      inputs.forEach(function (inp) {
        if ((parseFloat(inp.value) || 0) > 0) inp.classList.add("vec-error");
      });
      window.__pptalk_emo_vec = "";
      window.__pptalk_vec_valid = false;
    } else {
      statusEl.textContent = "向量之和: " + sum.toFixed(2) + " / " + VEC_MAX_SUM;
      statusEl.className = "patch-vec-status ok";
      window.__pptalk_emo_vec = JSON.stringify(vec);
      window.__pptalk_vec_valid = true;
    }
    return !hasError;
  }

  function createBgConfig() {
    var wrap = document.createElement("div");
    wrap.className = "patch-section";
    wrap.id = "patch-bg-section";

    var emoLabels = ["开心", "悲伤", "愤怒", "惊讶", "恐惧", "厌恶", "平静", "兴奋"];
    var vecInputs = emoLabels.map(function (lb, idx) {
      return '<div class="patch-vec-item"><label>' + lb + '</label>' +
        '<input type="number" step="0.1" min="0" max="' + VEC_MAX_EACH + '" value="0" data-idx="' + idx + '"></div>';
    }).join("");

    var curBgm = window.__pptalk_bgm_mode || "default";
    var curEmo = window.__pptalk_emo_method || "0";

    wrap.innerHTML =
      '<div class="patch-title">背景配置</div>' +
      '<div class="patch-row"><span class="patch-label">欢迎词</span>' +
      '<input class="patch-input" id="patch-welcome" value="' + (window.__pptalk_welcome_text || "欢迎来到云南水利水电职业技术学院") + '" placeholder="输入欢迎词"></div>' +
      '<div class="patch-row"><span class="patch-label">背景音乐</span>' +
      '<div class="patch-radio-group" id="patch-bgm-group">' +
      '<div class="patch-radio' + (curBgm === "default" ? ' active' : '') + '" data-val="default">默认</div>' +
      '<div class="patch-radio' + (curBgm === "custom" ? ' active' : '') + '" data-val="custom">自定义</div>' +
      '<div class="patch-radio' + (curBgm === "none" ? ' active' : '') + '" data-val="none">无</div>' +
      '</div></div>' +
      '<div class="patch-row" id="patch-bgm-upload-row" style="display:' + (curBgm === "custom" ? "flex" : "none") + ';">' +
      '<button class="patch-file-btn" id="patch-bgm-btn">选择音乐文件</button>' +
      '<span class="patch-file-name" id="patch-bgm-name">' + (window.__pptalk_bgm_path ? "已上传" : "") + '</span>' +
      '<input type="file" id="patch-bgm-file" accept=".mp3,.wav" style="display:none;">' +
      '</div>' +
      '<div class="patch-title" style="margin-top:18px;">TTS 情感控制</div>' +
      '<div class="patch-row"><span class="patch-label">控制方式</span>' +
      '<div class="patch-radio-group" id="patch-emo-group">' +
      '<div class="patch-radio' + (curEmo === "0" ? ' active' : '') + '" data-val="0">自然语调</div>' +
      '<div class="patch-radio' + (curEmo === "2" ? ' active' : '') + '" data-val="2">情感向量</div>' +
      '<div class="patch-radio' + (curEmo === "3" ? ' active' : '') + '" data-val="3">情感文本</div>' +
      '</div></div>' +
      '<div class="patch-emo-extra' + (curEmo === "2" ? ' visible' : '') + '" id="patch-emo-vec-area">' +
      '<div class="patch-hint">调整8维情感向量，每维范围 [0, ' + VEC_MAX_EACH + ']，总和不超过 ' + VEC_MAX_SUM + '</div>' +
      '<div class="patch-vec-grid" id="patch-vec-grid">' + vecInputs + '</div>' +
      '<div id="patch-vec-sum" class="patch-vec-status ok">向量之和: 0.00 / ' + VEC_MAX_SUM + '</div>' +
      '</div>' +
      '<div class="patch-emo-extra' + (curEmo === "3" ? ' visible' : '') + '" id="patch-emo-text-area">' +
      '<div class="patch-hint">用自然语言描述期望的语音情感</div>' +
      '<textarea class="patch-textarea" id="patch-emo-text" placeholder="例如：温柔且稍带兴奋的语气">' + (window.__pptalk_emo_text || "") + '</textarea></div>';

    wrap.querySelector("#patch-welcome").addEventListener("input", function (ev) {
      window.__pptalk_welcome_text = ev.target.value;
    });

    wrap.querySelector("#patch-bgm-group").addEventListener("click", function (ev) {
      var t = ev.target.closest(".patch-radio");
      if (!t) return;
      wrap.querySelectorAll("#patch-bgm-group .patch-radio").forEach(function (r) { r.classList.remove("active"); });
      t.classList.add("active");
      var val = t.dataset.val;
      window.__pptalk_bgm_mode = val;
      document.getElementById("patch-bgm-upload-row").style.display = val === "custom" ? "flex" : "none";
      if (val !== "custom") window.__pptalk_bgm_path = "";
    });

    wrap.querySelector("#patch-bgm-btn").addEventListener("click", function () {
      document.getElementById("patch-bgm-file").click();
    });

    wrap.querySelector("#patch-bgm-file").addEventListener("change", function (ev) {
      var file = ev.target.files[0];
      if (!file) return;
      document.getElementById("patch-bgm-name").textContent = file.name;
      var fd = new FormData();
      fd.append("file", file);
      var base = getBaseURL();
      fetch((base || "") + "/files/upload_bgm", { method: "POST", body: fd })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.code === 200) {
            window.__pptalk_bgm_path = data.data.bgm_path;
            document.getElementById("patch-bgm-name").textContent = "✓ " + file.name;
          } else {
            document.getElementById("patch-bgm-name").textContent = "上传失败";
          }
        })
        .catch(function () {
          document.getElementById("patch-bgm-name").textContent = "上传失败";
        });
    });

    wrap.querySelector("#patch-emo-group").addEventListener("click", function (ev) {
      var t = ev.target.closest(".patch-radio");
      if (!t) return;
      wrap.querySelectorAll("#patch-emo-group .patch-radio").forEach(function (r) { r.classList.remove("active"); });
      t.classList.add("active");
      var val = t.dataset.val;
      window.__pptalk_emo_method = val;
      document.getElementById("patch-emo-vec-area").classList.toggle("visible", val === "2");
      document.getElementById("patch-emo-text-area").classList.toggle("visible", val === "3");
      if (val === "0") {
        window.__pptalk_emo_vec = "";
        window.__pptalk_emo_text = "";
      }
    });

    wrap.querySelector("#patch-vec-grid").addEventListener("input", function () {
      validateVecInputs(wrap);
    });

    wrap.querySelector("#patch-vec-grid").addEventListener("change", function () {
      validateVecInputs(wrap);
    });

    wrap.querySelector("#patch-emo-text").addEventListener("input", function (ev) {
      window.__pptalk_emo_text = ev.target.value;
    });

    return wrap;
  }

  function tryInject() {
    var tabContents = document.querySelectorAll(".tab-content");
    if (tabContents.length < 1) return;

    tabContents.forEach(function (tab) {
      var title = tab.querySelector(".title");
      if (title) {
        var txt = title.textContent || "";
        if (txt.indexOf("讲稿") >= 0 && !tab.querySelector("#patch-style-section")) {
          var scrollArea = tab.querySelector(".script-scroll");
          if (scrollArea) {
            scrollArea.parentNode.insertBefore(createStyleSelector(), scrollArea);
          } else {
            var header = tab.querySelector(".content-header");
            if (header) header.after(createStyleSelector());
          }
        }
      }
      if (tab.classList.contains("template-tab") && !tab.querySelector("#patch-bg-section")) {
        var sections = tab.querySelectorAll(".module-section");
        if (sections.length > 0) {
          sections[sections.length - 1].after(createBgConfig());
        }
      }
    });
  }

  injectCSS();

  var debounceTimer = null;
  var observer = new MutationObserver(function () {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(tryInject, 80);
  });

  function startObserving() {
    var app = document.getElementById("app");
    if (app) {
      observer.observe(app, { childList: true, subtree: true });
      tryInject();
    } else {
      setTimeout(startObserving, 500);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserving);
  } else {
    startObserving();
  }
})();

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DigitalHuman, ScriptStyle, BgmMode } from '@/types'

export const useWorkflowStore = defineStore('workflow', () => {
  const fileId = ref('')
  const filePath = ref('')
  const fileName = ref('')
  const pdfPath = ref('')
  const imageUrls = ref<string[]>([])
  const originalFile = ref<File | null>(null)

  const scriptContent = ref('')
  const scriptStyle = ref<ScriptStyle>('normal')

  const selectedHuman = ref<DigitalHuman | null>(null)
  const template = ref('浮层-左下')
  const welcomeText = ref('欢迎来到云南水利水电职业技术学院')
  const bgmMode = ref<BgmMode>('default')
  const bgmPath = ref('')
  const emoControlMethod = ref<number>(0)
  const emoVec = ref('')
  const emoText = ref('')

  const outputFileName = ref('')

  const currentStep = ref(0)
  const maxVisitedStep = ref(0)

  function setUploadData(data: {
    fileId: string
    filePath: string
    fileName: string
    pdfPath: string
    imageUrls: string[]
    originalFile?: File | null
  }) {
    fileId.value = data.fileId
    filePath.value = data.filePath
    fileName.value = data.fileName
    pdfPath.value = data.pdfPath
    imageUrls.value = data.imageUrls
    if (data.originalFile !== undefined) {
      originalFile.value = data.originalFile
    }
  }

  function setScriptData(content: string, style: ScriptStyle) {
    scriptContent.value = content
    scriptStyle.value = style
  }

  function setTemplateData(data: {
    human: DigitalHuman | null
    template: string
    welcomeText: string
    bgmMode: BgmMode
    bgmPath: string
    emoControlMethod: number
    emoVec: string
    emoText: string
  }) {
    selectedHuman.value = data.human
    template.value = data.template
    welcomeText.value = data.welcomeText
    bgmMode.value = data.bgmMode
    bgmPath.value = data.bgmPath
    emoControlMethod.value = data.emoControlMethod
    emoVec.value = data.emoVec
    emoText.value = data.emoText
  }

  function setStep(step: number) {
    currentStep.value = step
    if (step > maxVisitedStep.value) {
      maxVisitedStep.value = step
    }
  }

  function canGoToStep(step: number): boolean {
    if (step <= currentStep.value) return true
    if (step > maxVisitedStep.value + 1) return false

    switch (step) {
      case 1: return !!pdfPath.value
      case 2: return !!scriptContent.value
      case 3: return !!selectedHuman.value
      default: return true
    }
  }

  function reset() {
    fileId.value = ''
    filePath.value = ''
    fileName.value = ''
    pdfPath.value = ''
    imageUrls.value = []
    originalFile.value = null
    scriptContent.value = ''
    scriptStyle.value = 'normal'
    selectedHuman.value = null
    template.value = '浮层-左下'
    welcomeText.value = '欢迎来到云南水利水电职业技术学院'
    bgmMode.value = 'default'
    bgmPath.value = ''
    emoControlMethod.value = 0
    emoVec.value = ''
    emoText.value = ''
    outputFileName.value = ''
    currentStep.value = 0
    maxVisitedStep.value = 0
  }

  function buildGenerationRequest() {
    return {
      scriptContent: scriptContent.value,
      human: selectedHuman.value,
      pdf_path: pdfPath.value,
      file_name: outputFileName.value || fileName.value,
      template: template.value,
      welcome_text: welcomeText.value,
      bgm_mode: bgmMode.value,
      bgm_path: bgmPath.value,
      emo_control_method: emoControlMethod.value,
      emo_vec: emoVec.value,
      emo_text: emoText.value,
    }
  }

  return {
    fileId, filePath, fileName, pdfPath, imageUrls, originalFile,
    scriptContent, scriptStyle,
    selectedHuman, template, welcomeText, bgmMode, bgmPath,
    emoControlMethod, emoVec, emoText,
    outputFileName,
    currentStep, maxVisitedStep,
    setUploadData, setScriptData, setTemplateData, setStep, canGoToStep, reset,
    buildGenerationRequest,
  }
})

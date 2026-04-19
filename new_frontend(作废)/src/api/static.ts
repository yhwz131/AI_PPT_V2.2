import axios from 'axios'
import type { DigitalHumanListResponse, BasicInformationResponse } from '@/types'

export function getBuiltInHumans() {
  return axios.get<DigitalHumanListResponse>('/static/Digital_human/Built-in_digital_human.json')
}

export function getCustomizedHumans() {
  return axios.get<DigitalHumanListResponse>('/static/Digital_human/Customized_digital_human.json')
}

export function getBasicInformation() {
  return axios.get<BasicInformationResponse>('/static/data/basic_information.json')
}

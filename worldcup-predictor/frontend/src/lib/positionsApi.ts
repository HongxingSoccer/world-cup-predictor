import { api, apiGet, apiPost } from './api';
import type {
  CreatePositionRequest,
  PositionResponse,
  PositionStatus,
  UpdateStatusRequest,
} from '@/types/positions';

const BASE = '/api/v1/positions';

export async function listPositions(status?: PositionStatus): Promise<PositionResponse[]> {
  const url = status ? `${BASE}?status=${encodeURIComponent(status)}` : BASE;
  return apiGet<PositionResponse[]>(url);
}

export async function getPosition(id: number): Promise<PositionResponse> {
  return apiGet<PositionResponse>(`${BASE}/${id}`);
}

export async function createPosition(body: CreatePositionRequest): Promise<PositionResponse> {
  return apiPost<PositionResponse, CreatePositionRequest>(BASE, body);
}

export async function updatePositionStatus(
  id: number,
  body: UpdateStatusRequest,
): Promise<PositionResponse> {
  const response = await api.patch<PositionResponse>(`${BASE}/${id}/status`, body);
  return response.data;
}

export async function deletePosition(id: number): Promise<PositionResponse> {
  const response = await api.delete<PositionResponse>(`${BASE}/${id}`);
  return response.data;
}

import { api, apiGet, apiPost } from './api';
import type {
  NotificationListResponse,
  NotificationResponse,
} from '@/types/positions';

const BASE = '/api/v1/notifications';

export async function listNotifications(limit = 50): Promise<NotificationListResponse> {
  return apiGet<NotificationListResponse>(`${BASE}?limit=${limit}`);
}

export async function getUnreadCount(): Promise<{ unreadCount: number }> {
  return apiGet<{ unreadCount: number }>(`${BASE}/unread-count`);
}

export async function markRead(id: number): Promise<NotificationResponse> {
  const response = await api.patch<NotificationResponse>(`${BASE}/${id}/read`);
  return response.data;
}

export async function markAllRead(): Promise<{ updated: number }> {
  return apiPost<{ updated: number }>(`${BASE}/read-all`);
}

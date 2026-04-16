import { therapistFetchJson } from "./therapistFetch";

export type NotificationChannel = "whatsapp" | "sms" | "both";

export interface CrisisSettings {
  user_id?: string;
  emergency_alerts_enabled: boolean;
  location_sharing_consent: boolean;
  consent_given_at?: string | null;
  consent_text_shown?: string | null;
  countdown_seconds: number;
  country_code: string;
  user_phone?: string | null;
  last_known_location?: { lat: number; lng: number; accuracy?: number; updated_at?: string } | null;
}

export interface CrisisSettingsUpdate {
  emergency_alerts_enabled: boolean;
  location_sharing_consent?: boolean;
  consent_text_shown: string;
  countdown_seconds?: number;
  country_code?: string;
  user_phone?: string | null;
}

export interface EmergencyContact {
  id: string;
  user_id: string;
  contact_name: string;
  contact_phone: string;
  relationship?: string | null;
  notification_channel: NotificationChannel;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ContactCreate {
  contact_name: string;
  contact_phone: string;
  relationship?: string;
  notification_channel?: NotificationChannel;
}

export interface ContactUpdate {
  contact_name?: string;
  contact_phone?: string;
  relationship?: string;
  notification_channel?: NotificationChannel;
  is_active?: boolean;
}

export interface CrisisEvent {
  event_id: string;
  severity: string;
  severity_score: number;
  intervention_type: string;
  emergency_alerts_sent: boolean;
  contacts_notified: string[];
  created_at: string;
  triggered_by: string;
}

export interface TestAlertResult {
  event_id: string;
  contacts_notified: number;
  results: Array<{ channel: string; to: string; success: boolean; error?: string }>;
}

const BASE = "/api/v1/crisis";

export const crisisApi = {
  getSettings: () => therapistFetchJson<CrisisSettings>(`${BASE}/settings`),
  updateSettings: (body: CrisisSettingsUpdate) =>
    therapistFetchJson<CrisisSettings>(`${BASE}/settings`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listContacts: () => therapistFetchJson<{ contacts: EmergencyContact[] }>(`${BASE}/contacts`),
  addContact: (body: ContactCreate) =>
    therapistFetchJson<EmergencyContact>(`${BASE}/contacts`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateContact: (id: string, body: ContactUpdate) =>
    therapistFetchJson<{ ok: true }>(`${BASE}/contacts/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteContact: (id: string) =>
    therapistFetchJson<{ ok: true }>(`${BASE}/contacts/${id}`, { method: "DELETE" }),

  cancelAlert: () =>
    therapistFetchJson<{ cancelled: number }>(`${BASE}/cancel-alert`, { method: "POST" }),

  listEvents: (limit = 50) =>
    therapistFetchJson<{ events: CrisisEvent[] }>(`${BASE}/events?limit=${limit}`),

  testAlert: () =>
    therapistFetchJson<TestAlertResult>(`${BASE}/test-alert`, { method: "POST" }),
};

export const E164_REGEX = /^\+[1-9][0-9]{6,14}$/;

export const DEFAULT_CONSENT_TEXT =
  "I consent to Ella by 3AM Talks notifying my listed emergency contacts via " +
  "WhatsApp/SMS if the system detects that I may be in immediate danger. I " +
  "understand a 30-second countdown lets me cancel the alert before it is sent.";

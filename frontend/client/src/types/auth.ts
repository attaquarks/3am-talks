// User type for authentication
export type UserRole = 'patient' | 'therapist' | 'admin';
export type AccountStatus = 'active' | 'suspended' | 'banned' | 'pending_verification';

export interface User {
    id: number | string;
    username: string;
    email?: string;
    createdAt?: Date | string;
    role?: UserRole;
    account_status?: AccountStatus;
    suspended_until?: string | null;
    admin_id?: string | null;
}

export enum AuthMode {
    LOGIN = 'LOGIN',
    SIGNUP = 'SIGNUP'
}

// Clinical portal types

export type LinkStatus = 'pending_therapist' | 'pending_patient' | 'active' | 'declined' | 'revoked' | 'expired';

export interface ConsentScope {
    conversations?: boolean;
    journals?: boolean;
    mood?: boolean;
    reports?: boolean;
    personality?: boolean;
}

export interface PatientTherapistLink {
    link_id: string;
    patient_id: string;
    therapist_id: string;
    status: LinkStatus;
    initiated_by: string;
    patient_consented_at?: string | null;
    therapist_consented_at?: string | null;
    consent_scope?: ConsentScope;
    revoked_at?: string | null;
    revoked_by?: string | null;
    revoke_reason?: string | null;
    created_at?: string;
    updated_at?: string;
    counterparty?: {
        user_id: string;
        name?: string;
        email?: string;
        display_name?: string;
        title?: string;
        specializations?: string[];
        modalities?: string[];
        photo_url?: string;
        bio?: string;
    };
}

export interface TherapistProfile {
    therapist_user_id: string;
    display_name?: string;
    title?: string;
    license_number?: string;
    license_jurisdiction?: string;
    license_verified_at?: string;
    specializations?: string[];
    modalities?: string[];
    languages?: string[];
    years_experience?: number;
    bio?: string;
    pronouns?: string;
    photo_url?: string;
    accepting_patients?: boolean;
    max_caseload?: number;
    timezone?: string;
    availability?: Record<string, unknown>;
}

export interface CaseloadPatient {
    link_id: string;
    patient_id: string;
    name?: string;
    email?: string;
    linked_since?: string;
    last_session_at?: string | null;
    total_sessions: number;
    recent_mood: Array<{ date?: string; mood?: string }>;
    risk_level: string;
    unresolved_crisis: boolean;
}

export interface SessionSummary {
    summary_id?: string;
    conversation_id: string;
    patient_id?: string;
    subjective?: string;
    objective?: string;
    assessment?: string;
    plan?: string;
    themes?: string[];
    action_items?: string[];
    mood_trajectory?: string;
    risk_flags?: {
        flagged?: boolean;
        severity?: string;
        categories?: Record<string, string[]>;
        snippets?: string[];
    };
    generated_at?: string;
    therapist_reviewed?: boolean;
}

export interface TherapistNote {
    note_id: string;
    therapist_id: string;
    patient_id: string;
    conversation_id?: string | null;
    body: string;
    tags?: string[];
    follow_up_at?: string | null;
    created_at?: string;
    updated_at?: string;
}

export interface TreatmentPlan {
    plan_id: string;
    therapist_id: string;
    patient_id: string;
    title: string;
    primary_concern?: string;
    goals?: Array<{ goal: string; milestones?: string[]; target_date?: string; status?: string }>;
    interventions?: string[];
    status: 'active' | 'paused' | 'completed' | 'archived';
    created_at?: string;
    updated_at?: string;
}

export interface HomeworkItem {
    homework_id: string;
    therapist_id: string;
    patient_id: string;
    plan_id?: string | null;
    title: string;
    description?: string;
    due_at?: string | null;
    status: 'assigned' | 'in_progress' | 'completed' | 'skipped';
    patient_reflection?: string | null;
    completed_at?: string | null;
    created_at?: string;
    therapist_name?: string;
}

export interface SecureMessage {
    message_id: string;
    thread_id: string;
    link_id: string;
    sender_id: string;
    recipient_id: string;
    body: string;
    urgency: 'normal' | 'priority' | 'urgent';
    is_system?: boolean;
    read_at?: string | null;
    created_at?: string;
}

export interface CrisisEvent {
    event_id: string;
    patient_id: string;
    therapist_id?: string;
    triggered_by: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    severity_score?: number;
    trigger_text?: string | null;
    keyword_matches?: string[];
    intervention_type?: string;
    session_id?: string | null;
    context?: Record<string, unknown>;
    escalated_at?: string;
    resolved_at?: string | null;
    resolution_notes?: string;
    created_at?: string;
}

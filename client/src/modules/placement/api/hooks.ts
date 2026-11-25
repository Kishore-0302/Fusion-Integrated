/** Data access for the placement module.
 *
 *  Every mutation invalidates the keys it can affect; no manual cache surgery.
 *  Getting that subtly wrong shows up as an enabled "Apply" button on a
 *  posting the student already applied to.
 */
import {
  useMutation, useQuery, useQueryClient, type UseMutationOptions,
} from "@tanstack/react-query";

import { filenameFromDisposition, saveBlob } from "../../../lib/download";
import { http, readBlobError } from "../../../lib/http";
import type {
  Announcement, Applicant, Application, Company, EligibilityVerdict,
  InterviewRound, Offer, Page, Posting, ProfileDocument, StaffStats,
  StudentStats,
} from "./types";

const KEY = "placement";

export const keys = {
  postings: (f?: unknown) => [KEY, "postings", f] as const,
  posting: (id: number) => [KEY, "posting", id] as const,
  eligibility: (id: number) => [KEY, "eligibility", id] as const,
  applications: (f?: unknown) => [KEY, "applications", f] as const,
  offers: () => [KEY, "offers"] as const,
  resume: () => [KEY, "resume"] as const,
  companies: () => [KEY, "companies"] as const,
  rounds: (postingId?: number) => [KEY, "rounds", postingId] as const,
  announcements: () => [KEY, "announcements"] as const,
  stats: (season?: string) => [KEY, "stats", season] as const,
  seasons: () => [KEY, "seasons"] as const,
  registrations: () => [KEY, "registrations"] as const,
  records: () => [KEY, "records"] as const,
  clearance: () => [KEY, "clearance"] as const,
  outstanding: (season?: string) => [KEY, "outstanding", season] as const,
  history: (id: number) => [KEY, "history", id] as const,
  myConduct: () => [KEY, "my-conduct"] as const,
  registrationTerms: (season?: string) =>
    [KEY, "registration-terms", season] as const,
};

/** Coarse on purpose — these pages are small, and correctness beats shaving
 *  a refetch. */
function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: [KEY] });
}

// -- Postings ------------------------------------------------------------------
export function usePostings(filters?: { placement_year?: string; kind?: string }) {
  return useQuery({
    queryKey: keys.postings(filters),
    queryFn: async () =>
      (await http.get<Page<Posting>>("/placement/postings", { params: filters }))
        .data,
    staleTime: 30_000,
  });
}

export function usePosting(id: number | undefined) {
  return useQuery({
    queryKey: keys.posting(id!),
    queryFn: async () =>
      (await http.get<Posting>(`/placement/postings/${id}`)).data,
    enabled: id != null,
  });
}

/** The "why can't I apply?" call, fetched when a posting is opened.
 *
 *  Deliberately not folded into the list query — it reaches the IAM for a
 *  declared CPI, so per-row would be fifty round trips nobody asked for. */
export function useEligibility(postingId: number | undefined) {
  return useQuery({
    queryKey: keys.eligibility(postingId!),
    queryFn: async () =>
      (await http.get<EligibilityVerdict>(
        `/placement/postings/${postingId}/eligibility`)).data,
    enabled: postingId != null,
    retry: false,     // a 503 from the IAM should surface, not be retried away
    staleTime: 60_000,
  });
}

export function useCreatePosting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<Posting>("/placement/postings", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function usePublishPosting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await http.post<Posting>(`/placement/postings/${id}/publish`, {})).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Applications --------------------------------------------------------------
export function useApplications(filters?: { status?: string; posting?: number }) {
  return useQuery({
    queryKey: keys.applications(filters),
    queryFn: async () =>
      (await http.get<Page<Application & Applicant>>(
        "/placement/applications", { params: filters })).data,
    staleTime: 15_000,
  });
}

export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { posting_id: number; cover_note?: string }) =>
      (await http.post<Application>("/placement/applications/apply", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useTransition(
  options?: Pick<UseMutationOptions<Application, unknown,
    { id: number; to_status: string; reason?: string }>, "onSuccess" | "onError">,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, to_status, reason }:
      { id: number; to_status: string; reason?: string }) =>
      (await http.post<Application>(
        `/placement/applications/${id}/transition`,
        { to_status, reason: reason ?? "" })).data,
    onSuccess: (...args) => { invalidateAll(qc); options?.onSuccess?.(...args); },
    onError: options?.onError,
  });
}

// -- Offers --------------------------------------------------------------------
export function useOffers() {
  return useQuery({
    queryKey: keys.offers(),
    queryFn: async () => (await http.get<Page<Offer>>("/placement/offers")).data,
    // Short: an expired offer must not keep rendering an enabled Accept button.
    staleTime: 10_000,
  });
}

export function useIssueOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      application_id: number; ctc_lpa?: string; respond_by?: string;
    }) => (await http.post<Offer>("/placement/offers/issue", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useRespondToOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept }: { id: number; accept: boolean }) =>
      (await http.post<Offer>(`/placement/offers/${id}/respond`, { accept })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Profile -------------------------------------------------------------------



// -- Companies -----------------------------------------------------------------
export function useCompanies() {
  return useQuery({
    queryKey: keys.companies(),
    queryFn: async () =>
      (await http.get<Page<Company>>("/placement/companies")).data,
    staleTime: 30_000,
  });
}

export function useRegisterCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<Company>("/placement/companies", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useCompanyDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action, note }: {
      id: number; action: "approve" | "reject" | "blacklist"; note?: string;
    }) => (await http.post<Company>(
      `/placement/companies/${id}/${action}`, { note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useInviteRecruiter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      company_id: number; email: string; full_name?: string;
    }) => (await http.post<{
      account_id: number; email: string; invite_token: string;
      expires_at: string;
    }>("/placement/recruiters/invite", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Interviews ----------------------------------------------------------------
export function useRounds(postingId?: number) {
  return useQuery({
    queryKey: keys.rounds(postingId),
    queryFn: async () =>
      (await http.get<Page<InterviewRound>>("/placement/interviews/rounds",
        { params: postingId ? { posting: postingId } : undefined })).data,
    staleTime: 30_000,
  });
}

export function useScheduleRound() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<InterviewRound>("/placement/interviews/rounds", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useAddCandidates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ roundId, applicationIds }: {
      roundId: number; applicationIds: number[];
    }) => (await http.post<{ scheduled: number }>(
      `/placement/interviews/rounds/${roundId}/candidates`,
      { application_ids: applicationIds })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Announcements -------------------------------------------------------------
export function useAnnouncements() {
  return useQuery({
    queryKey: keys.announcements(),
    queryFn: async () =>
      (await http.get<Page<Announcement>>("/placement/announcements")).data,
    staleTime: 30_000,
  });
}

export function usePublishAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<Announcement>("/placement/announcements", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useWithdrawAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) =>
      (await http.post<Announcement>(
        `/placement/announcements/${id}/withdraw`, { reason })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Statistics ----------------------------------------------------------------
export function useStats(season?: string) {
  return useQuery({
    queryKey: keys.stats(season),
    queryFn: async () =>
      (await http.get<StudentStats & StaffStats>("/placement/stats",
        { params: season ? { season } : undefined })).data,
    staleTime: 60_000,
  });
}

// -- Documents -----------------------------------------------------------------
export function useMyDocuments() {
  return useQuery({
    queryKey: [KEY, "documents"],
    queryFn: async () =>
      (await http.get<{ results: ProfileDocument[] }>("/placement/documents")).data,
  });
}

/** Attach a Drive link. The server rebuilds the URL from the file id. */
export function useAttachDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { url: string; kind: string; title?: string }) =>
      (await http.post<ProfileDocument>("/placement/documents", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => http.delete(`/placement/documents/${id}`),
    onSuccess: () => invalidateAll(qc),
  });
}

/** The authorising view. The raw Drive URL is absent from list payloads. */
export function documentDownloadUrl(id: number): string {
  return `/api/v1/placement/documents/${id}/download`;
}

export type ExportKind = "applications" | "placements";

const EXPORT_PATHS: Record<ExportKind, string> = {
  applications: "/placement/exports/applications.csv",
  placements: "/placement/exports/placements.csv",
};

/** Exports are fetched, not navigated to. A link would leave the SPA, so a
 *  refused or throttled export lands the officer on a raw server error page;
 *  buffering a capped file is the cost of reporting it as a toast instead. */
export function useCsvExport() {
  return useMutation({
    mutationFn: async (kind: ExportKind) => {
      try {
        const res = await http.get(EXPORT_PATHS[kind], { responseType: "blob" });
        saveBlob(
          res.data as Blob,
          filenameFromDisposition(
            res.headers["content-disposition"], `${kind}.csv`),
        );
      } catch (e) {
        throw await readBlobError(e);
      }
    },
  });
}

// -- Audit trail (PC-AFR-009) --------------------------------------------------
export interface TransitionEntry {
  from_status: string;
  to_status: string;
  at: string;
  /** The lane — staff, student, recruiter, system — never the person. */
  actor_label: string;
  /** Absent for a non-staff reader; see api/audit.py. */
  reason?: string;
  actor_user_id?: number | null;
}

export interface TransitionHistory {
  application_id: number;
  /** True when reasons and actor identities were withheld, so the UI can say
   *  so rather than implying the trail is empty. */
  redacted: boolean;
  results: TransitionEntry[];
}

export function useApplicationHistory(id: number | undefined) {
  return useQuery({
    queryKey: keys.history(id ?? 0),
    queryFn: async () => (await http.get<TransitionHistory>(
      `/placement/applications/${id}/history`)).data,
    enabled: Boolean(id),
  });
}

export interface MyConductIncident {
  id: number;
  kind: string;
  note: string;
  waived: boolean;
  waived_reason: string;
  created_at: string;
}

/** A student's own conduct record, shown in full — rule 19's waiver and rule
 *  21's sanction are both contestable. */
export function useMyConductRecord() {
  return useQuery({
    queryKey: keys.myConduct(),
    queryFn: async () => (await http.get<Page<MyConductIncident>>(
      "/placement/conduct/mine")).data,
  });
}

/** Move several applications at once. Each item is authorised individually on
 *  the server, so a refusal for one does not stop the rest. */
export interface BulkOutcome {
  application_id: number;
  moved: boolean;
  error: string;
  code: string;
}

export interface BulkResult {
  moved: number;
  refused: number;
  results: BulkOutcome[];
}

export function useBulkTransition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      application_ids: number[]; to_status: string; reason?: string;
    }) => (await http.post<BulkResult>(
      "/placement/applications/bulk-transition", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Post-offer obligations (rules 22, 24) -------------------------------------
export interface PlacementRecordRow {
  id: number;
  company: { id: number; name: string } | null;
  source: "campus" | "off_campus";
  kind: string;
  ctc_lpa: string | null;
  offer_letter_submitted: boolean;
  offer_letter_submitted_at: string | null;
  not_joining_declared_at: string | null;
  not_joining_reason: string;
  not_joining_was_late: boolean;
  created_at: string;
}

export interface Clearance {
  user_id: number;
  cleared: boolean;
  /** Each company still owing a signed letter, so a hold is actionable. */
  blocking: string[];
  message: string;
}

export function useMyRecords() {
  return useQuery({
    queryKey: keys.records(),
    queryFn: async () =>
      (await http.get<Page<PlacementRecordRow>>("/placement/records")).data,
  });
}

/** Rule 24. The hold on a no-dues certificate, and why. */
export function useMyClearance() {
  return useQuery({
    queryKey: keys.clearance(),
    queryFn: async () =>
      (await http.get<Clearance>("/placement/records/clearance")).data,
  });
}

export function useSubmitOfferLetter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { recordId: number; document_id: number }) =>
      (await http.post<PlacementRecordRow>(
        `/placement/records/${body.recordId}/offer-letter`,
        { document_id: body.document_id })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export interface NotJoiningResult {
  is_late: boolean;
  message: string;
}

export function useDeclareNotJoining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { recordId: number; reason: string }) =>
      (await http.post<NotJoiningResult>(
        `/placement/records/${body.recordId}/not-joining`,
        { reason: body.reason })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

/** Staff: placed students who still owe a signed letter. */
export function useOutstandingLetters(season?: string) {
  return useQuery({
    queryKey: keys.outstanding(season),
    queryFn: async () => (await http.get<Page<PlacementRecordRow>>(
      "/placement/records/outstanding", { params: season ? { season } : {} })).data,
  });
}

// -- Registration (rules 1, 20, 21) --------------------------------------------
export interface Registration {
  id: number;
  policy: number;
  season: string;
  status: "registered" | "debarred" | "opted_out";
  offer_count: number;
  registered_late: boolean;
  registered_at: string | null;
  debarred_reason: string;
}

export interface RegistrationTerms {
  /** open | late | reregister | refused — `late` and `reregister` are real
   *  routes that go through the Placement Cell, not refusals. */
  route: "open" | "late" | "reregister" | "refused";
  reason: string;
  message: string;
  /** Rupees the student must already have paid. Recorded, never collected. */
  fee: number;
  allowed: boolean;
}

export function useMyRegistrations() {
  return useQuery({
    queryKey: keys.registrations(),
    queryFn: async () =>
      (await http.get<Page<Registration>>("/placement/registrations")).data,
  });
}

export function useRegistrationTerms(season: string | undefined) {
  return useQuery({
    queryKey: keys.registrationTerms(season),
    queryFn: async () => (await http.get<RegistrationTerms>(
      "/placement/registrations/terms", { params: { season } })).data,
    enabled: Boolean(season),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (season: string) =>
      (await http.post<Registration>("/placement/registrations",
                                     { season })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useOptOut() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { season: string; reason?: string }) =>
      (await http.post<Registration>("/placement/registrations/opt-out",
                                     body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

/** Staff: rule 20's late approval and rule 21's one re-registration. */
export function useApproveLate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      season: string; user_id: number; fee_reference: string;
    }) => (await http.post<Registration>(
      "/placement/registrations/approve-late", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useReRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      season: string; user_id: number; fee_reference: string;
    }) => (await http.post<Registration>(
      "/placement/registrations/re-register", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Seasons -------------------------------------------------------------------
export interface Season {
  season: string;
  label: string;
  is_active: boolean;
}

/** The seasons a posting may belong to. A closed list, because a season with
 *  no PlacementPolicy behind it fails only when a student tries to apply. */
export function useSeasons() {
  return useQuery({
    queryKey: keys.seasons(),
    queryFn: async () => (await http.get<Season[]>("/placement/seasons")).data,
    staleTime: 10 * 60_000,
  });
}

// -- CPI directory (staff only) ------------------------------------------------
export interface CpiRow {
  user_id: number;
  roll_no: string;
  name: string;
  discipline: string;
  programme: string;
  batch_year: number | null;
  /** null = no DECLARED result. Never render this as 0.00. */
  cpi: string | null;
  earned_credits: string | null;
  active_backlogs: number | null;
  semester: number | null;
  semester_type: string | null;
  synced_at: string | null;
}

export interface CpiPage {
  count: number;
  limit: number;
  offset: number;
  results: CpiRow[];
}

export function useCpiDirectory(filters: {
  q?: string; discipline?: string; batch_year?: string; programme?: string;
  only_declared?: boolean; limit?: number; offset?: number;
}) {
  return useQuery({
    queryKey: [KEY, "cpi", filters],
    queryFn: async () =>
      (await http.get<CpiPage>("/placement/students/cpi", { params: filters })).data,
    // Declared results change only on an exam-office announcement.
    staleTime: 120_000,
    placeholderData: (prev) => prev,      // no flicker while typing a search
  });
}

export function useCpiFilters() {
  return useQuery({
    queryKey: [KEY, "cpi-filters"],
    queryFn: async () =>
      (await http.get<{
        disciplines: string[]; batch_years: number[]; programmes: string[];
      }>("/placement/students/cpi/filters")).data,
    staleTime: 600_000,
  });
}

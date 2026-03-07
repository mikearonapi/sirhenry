"use client";
import { useCallback, useEffect, useState } from "react";
import { Loader2, AlertCircle, Plus, Trash2, Users } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import {
  createHouseholdProfile, updateHouseholdProfile,
  getFamilyMembers, createFamilyMember, updateFamilyMember, deleteFamilyMember,
  getFamilyMilestones,
} from "@/lib/api";
import type {
  HouseholdProfile, HouseholdProfileIn, FamilyMember, FamilyMemberIn,
  FamilyMilestone, OtherIncomeSource,
} from "@/types/api";
import Card from "@/components/ui/Card";
import { FILING_OPTIONS } from "./constants";
import HouseholdProfileForm from "./HouseholdProfileForm";
import FamilyMemberList from "./FamilyMemberList";

// ---------------------------------------------------------------------------
// ProfileTab — main orchestrator
// ---------------------------------------------------------------------------

export interface ProfileTabProps {
  profiles: HouseholdProfile[];
  loading: boolean;
  error: string | null;
  onError: (e: string) => void;
  onReload: () => void;
  onDelete: (id: number) => void;
}

export default function ProfileTab({
  profiles, loading, error, onError, onReload, onDelete,
}: ProfileTabProps) {
  const [showHHForm, setShowHHForm] = useState(false);
  const [editHHId, setEditHHId] = useState<number | null>(null);
  const [hhSaving, setHHSaving] = useState(false);
  const [formName, setFormName] = useState("");
  const [formFilingStatus, setFormFilingStatus] = useState("mfj");
  const [formState, setFormState] = useState("");
  const [otherSources, setOtherSources] = useState<OtherIncomeSource[]>([]);

  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [milestones, setMilestones] = useState<FamilyMilestone[]>([]);

  const primaryProfile = profiles.find((p) => p.is_primary) || profiles[0] || null;

  const loadMembersAndMilestones = useCallback(async (profileId: number) => {
    setMembersLoading(true);
    try {
      const [mems, miles] = await Promise.all([
        getFamilyMembers(profileId),
        getFamilyMilestones(profileId),
      ]);
      setMembers(Array.isArray(mems) ? mems : []);
      setMilestones(Array.isArray(miles) ? miles : []);
    } catch { /* non-fatal */ }
    finally { setMembersLoading(false); }
  }, []);

  useEffect(() => {
    if (primaryProfile) loadMembersAndMilestones(primaryProfile.id);
  }, [primaryProfile?.id, loadMembersAndMilestones]);

  function startEditHH(p: HouseholdProfile) {
    setEditHHId(p.id);
    setFormName(p.name);
    setFormFilingStatus(p.filing_status);
    setFormState(p.state || "");
    try {
      setOtherSources(p.other_income_sources_json ? JSON.parse(p.other_income_sources_json) : []);
    } catch { setOtherSources([]); }
    setShowHHForm(true);
  }

  async function saveHousehold() {
    setHHSaving(true);
    try {
      const totalOther = otherSources.reduce((s, x) => s + x.amount, 0);
      const body: HouseholdProfileIn = {
        name: formName || "My Household",
        filing_status: formFilingStatus,
        state: formState || null,
        other_income_annual: totalOther || null,
        other_income_sources_json: otherSources.length > 0 ? JSON.stringify(otherSources) : null,
      };
      if (editHHId) {
        await updateHouseholdProfile(editHHId, body);
      } else {
        await createHouseholdProfile(body);
      }
      await onReload();
      setShowHHForm(false);
      setEditHHId(null);
    } catch (e: unknown) { onError(e instanceof Error ? e.message : String(e)); }
    finally { setHHSaving(false); }
  }

  async function handleSaveMember(memberId: number | null, form: Omit<FamilyMemberIn, "household_id">) {
    if (!primaryProfile) return;
    if (memberId) {
      await updateFamilyMember(memberId, form);
    } else {
      await createFamilyMember({ ...form, household_id: primaryProfile.id });
    }
    await Promise.all([onReload(), loadMembersAndMilestones(primaryProfile.id)]);
  }

  async function handleDeleteMember(id: number) {
    if (!primaryProfile) return;
    try {
      await deleteFamilyMember(id);
      await Promise.all([onReload(), loadMembersAndMilestones(primaryProfile.id)]);
    } catch (e: unknown) { onError(e instanceof Error ? e.message : String(e)); }
  }

  if (loading) {
    return <div className="flex items-center gap-2 text-text-secondary text-sm py-8"><Loader2 size={16} className="animate-spin" />Loading...</div>;
  }

  return (
    <div className="space-y-6">
      {error && <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 p-3 rounded-lg flex items-center gap-2"><AlertCircle size={14} />{error}</div>}

      {!primaryProfile ? (
        <Card padding="lg">
          <div className="text-center py-6 space-y-3">
            <Users size={36} className="mx-auto text-text-muted" />
            <p className="text-sm text-text-secondary">Create your household to get started.</p>
            <button onClick={() => { setFormName("My Household"); setFormFilingStatus("mfj"); setFormState(""); setShowHHForm(true); }}
              className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover mx-auto">
              <Plus size={14} /> Create Household
            </button>
          </div>
          {showHHForm && (
            <div className="mt-4 pt-4 border-t border-card-border">
              <HouseholdProfileForm
                formName={formName}
                formFilingStatus={formFilingStatus}
                formState={formState}
                otherSources={otherSources}
                showOtherIncome={false}
                saving={hhSaving}
                onFormNameChange={setFormName}
                onFilingStatusChange={setFormFilingStatus}
                onStateChange={setFormState}
                onOtherSourcesChange={setOtherSources}
                onSave={saveHousehold}
                onCancel={() => setShowHHForm(false)}
              />
            </div>
          )}
        </Card>
      ) : (
        <>
          <Card padding="md">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-text-primary">{primaryProfile.name}</h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  {FILING_OPTIONS.find((o) => o.value === primaryProfile.filing_status)?.label}
                  {primaryProfile.state ? ` · ${primaryProfile.state}` : ""}
                  {" · "}W-2 wages: <span className="font-semibold text-text-secondary">{formatCurrency(primaryProfile.combined_income, true)}</span>
                  {primaryProfile.other_income_annual ? (
                    <span className="ml-1">· Other: <span className="font-semibold text-purple-700">{formatCurrency(primaryProfile.other_income_annual, true)}</span></span>
                  ) : null}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => startEditHH(primaryProfile)}
                  className="text-xs text-text-secondary hover:text-text-primary px-3 py-1.5 border border-border rounded-lg hover:border-border">
                  Edit Settings
                </button>
                <button onClick={() => onDelete(primaryProfile.id)}
                  className="text-xs text-text-muted hover:text-red-500 p-1.5 rounded-lg border border-border hover:border-red-200">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>

            {showHHForm && editHHId === primaryProfile.id && (
              <div className="mt-4 pt-4 border-t border-card-border">
                <HouseholdProfileForm
                  formName={formName}
                  formFilingStatus={formFilingStatus}
                  formState={formState}
                  otherSources={otherSources}
                  showOtherIncome={true}
                  saving={hhSaving}
                  onFormNameChange={setFormName}
                  onFilingStatusChange={setFormFilingStatus}
                  onStateChange={setFormState}
                  onOtherSourcesChange={setOtherSources}
                  onSave={saveHousehold}
                  onCancel={() => { setShowHHForm(false); setEditHHId(null); }}
                />
              </div>
            )}
          </Card>

          <FamilyMemberList
            profile={primaryProfile}
            members={members}
            membersLoading={membersLoading}
            milestones={milestones}
            onSaveMember={handleSaveMember}
            onDeleteMember={handleDeleteMember}
          />
        </>
      )}
    </div>
  );
}

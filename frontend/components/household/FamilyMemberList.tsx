"use client";
import { useState } from "react";
import { Loader2, Plus, Trash2, Users, Info } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { FamilyMember, FamilyMemberIn, FamilyMilestone, HouseholdProfile } from "@/types/api";
import Card from "@/components/ui/Card";
import {
  RELATIONSHIP_OPTIONS, REL_ICON, REL_COLOR,
  MILESTONE_CATEGORY_COLOR, calcAge, emptyMemberForm,
} from "./constants";

// ---------------------------------------------------------------------------
// FamilyMemberList — table of family members + add/edit/delete + milestones
// ---------------------------------------------------------------------------

export interface FamilyMemberListProps {
  profile: HouseholdProfile;
  members: FamilyMember[];
  membersLoading: boolean;
  milestones: FamilyMilestone[];
  onSaveMember: (memberId: number | null, form: Omit<FamilyMemberIn, "household_id">) => Promise<void>;
  onDeleteMember: (id: number) => Promise<void>;
}

export default function FamilyMemberList({
  profile,
  members,
  membersLoading,
  milestones,
  onSaveMember,
  onDeleteMember,
}: FamilyMemberListProps) {
  const [showMemberForm, setShowMemberForm] = useState(false);
  const [editMemberId, setEditMemberId] = useState<number | null>(null);
  const [memberSaving, setMemberSaving] = useState(false);
  const [memberForm, setMemberForm] = useState<Omit<FamilyMemberIn, "household_id">>(emptyMemberForm());

  function openAddMember() {
    setEditMemberId(null);
    setMemberForm(emptyMemberForm());
    setShowMemberForm(true);
  }

  function openEditMember(m: FamilyMember) {
    setEditMemberId(m.id);
    setMemberForm({
      name: m.name,
      relationship: m.relationship,
      date_of_birth: m.date_of_birth,
      ssn_last4: m.ssn_last4,
      is_earner: m.is_earner,
      income: m.income,
      employer: m.employer,
      work_state: m.work_state,
      employer_start_date: m.employer_start_date,
      grade_level: m.grade_level,
      school_name: m.school_name,
      care_cost_annual: m.care_cost_annual,
      college_start_year: m.college_start_year,
      notes: m.notes,
    });
    setShowMemberForm(true);
  }

  async function saveMember() {
    setMemberSaving(true);
    try {
      await onSaveMember(editMemberId, memberForm);
      setShowMemberForm(false);
      setEditMemberId(null);
    } finally {
      setMemberSaving(false);
    }
  }

  const isEarnerRole = memberForm.relationship === "self" || memberForm.relationship === "spouse";

  return (
    <>
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary">Family Members</h3>
          <button onClick={openAddMember}
            className="flex items-center gap-2 bg-accent text-white px-3 py-2 rounded-lg text-xs font-medium hover:bg-accent-hover">
            <Plus size={13} /> Add Member
          </button>
        </div>

        {membersLoading ? (
          <div className="flex items-center gap-2 text-text-secondary text-sm py-4"><Loader2 size={14} className="animate-spin" />Loading family members...</div>
        ) : members.length === 0 ? (
          <div className="p-6 border-2 border-dashed border-border rounded-xl text-center">
            <Users size={28} className="mx-auto text-text-muted mb-2" />
            <p className="text-sm text-text-secondary">No family members yet.</p>
            <p className="text-xs text-text-muted mt-1">Add yourself, your spouse, and each child to get personalized planning insights.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {members.map((m) => {
              const age = calcAge(m.date_of_birth);
              const color = REL_COLOR[m.relationship] || REL_COLOR.other;
              return (
                <div key={m.id} className={`relative p-4 rounded-xl border ${color} group`}>
                  <div className="absolute top-2 right-2 hidden group-hover:flex items-center gap-1">
                    <button onClick={() => openEditMember(m)} className="p-1 text-text-muted hover:text-text-secondary bg-card rounded border border-border">
                      <Info size={11} />
                    </button>
                    <button onClick={() => onDeleteMember(m.id)} className="p-1 text-text-muted hover:text-red-500 bg-card rounded border border-border">
                      <Trash2 size={11} />
                    </button>
                  </div>
                  <div className="text-2xl mb-1">{REL_ICON[m.relationship]}</div>
                  <p className="font-semibold text-text-primary text-sm truncate">{m.name}</p>
                  <p className="text-xs text-text-secondary capitalize">{RELATIONSHIP_OPTIONS.find((r) => r.value === m.relationship)?.label || m.relationship}</p>
                  {age !== null && <p className="text-xs text-text-secondary mt-1">Age {age}</p>}
                  {m.is_earner && m.income != null && (
                    <p className="text-xs font-semibold text-text-secondary mt-1">{formatCurrency(m.income, true)}</p>
                  )}
                  {m.employer && <p className="text-xs text-text-muted truncate mt-0.5">{m.employer}</p>}
                  {m.work_state && profile.state && m.work_state !== profile.state && (
                    <p className="text-xs text-amber-600 mt-0.5">Works in {m.work_state}</p>
                  )}
                  {m.grade_level && <p className="text-xs text-text-muted mt-0.5">{m.grade_level}</p>}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showMemberForm && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-4">
            {editMemberId ? "Edit" : "Add"} Family Member
          </h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-text-secondary">Name</label>
                <input type="text" value={memberForm.name}
                  onChange={(e) => setMemberForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
              <div>
                <label className="text-xs text-text-secondary">Relationship</label>
                <select value={memberForm.relationship}
                  onChange={(e) => {
                    const rel = e.target.value as FamilyMemberIn["relationship"];
                    const isEarner = rel === "self" || rel === "spouse";
                    setMemberForm((f) => ({ ...f, relationship: rel, is_earner: isEarner }));
                  }}
                  className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20">
                  {RELATIONSHIP_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-text-secondary">Date of Birth</label>
                <input type="date" value={memberForm.date_of_birth || ""}
                  onChange={(e) => setMemberForm((f) => ({ ...f, date_of_birth: e.target.value || null }))}
                  className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
              <div>
                <label className="text-xs text-text-secondary">SSN Last 4 (optional)</label>
                <input type="text" value={memberForm.ssn_last4 || ""} maxLength={4}
                  onChange={(e) => setMemberForm((f) => ({ ...f, ssn_last4: e.target.value || null }))}
                  placeholder="XXXX"
                  className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
              </div>
            </div>

            {isEarnerRole && (
              <div className="p-4 bg-surface rounded-xl border border-card-border space-y-3">
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">Employment</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-text-secondary">Annual Gross Income</label>
                    <input type="number" value={memberForm.income ?? ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, income: Number(e.target.value) || null, is_earner: true }))}
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                  <div>
                    <label className="text-xs text-text-secondary">Employer</label>
                    <input type="text" value={memberForm.employer || ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, employer: e.target.value || null }))}
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                  <div>
                    <label className="text-xs text-text-secondary">Work State (if different from home)</label>
                    <input type="text" value={memberForm.work_state || ""} maxLength={2}
                      onChange={(e) => setMemberForm((f) => ({ ...f, work_state: e.target.value.toUpperCase() || null }))}
                      placeholder="e.g. NY"
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 uppercase" />
                  </div>
                  <div>
                    <label className="text-xs text-text-secondary">Employment Start Date</label>
                    <input type="date" value={memberForm.employer_start_date || ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, employer_start_date: e.target.value || null }))}
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                </div>
              </div>
            )}

            {(memberForm.relationship === "child" || memberForm.relationship === "other_dependent") && (
              <div className="p-4 bg-surface rounded-xl border border-card-border space-y-3">
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">Education & Care</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-text-secondary">Grade Level / School Year</label>
                    <input type="text" value={memberForm.grade_level || ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, grade_level: e.target.value || null }))}
                      placeholder="e.g. 3rd grade, Kindergarten, Freshman"
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                  <div>
                    <label className="text-xs text-text-secondary">School Name</label>
                    <input type="text" value={memberForm.school_name || ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, school_name: e.target.value || null }))}
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                  <div>
                    <label className="text-xs text-text-secondary">Annual Care / Childcare Cost</label>
                    <input type="number" value={memberForm.care_cost_annual ?? ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, care_cost_annual: Number(e.target.value) || null }))}
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                  <div>
                    <label className="text-xs text-text-secondary">Estimated College Start Year</label>
                    <input type="number" value={memberForm.college_start_year ?? ""}
                      onChange={(e) => setMemberForm((f) => ({ ...f, college_start_year: Number(e.target.value) || null }))}
                      placeholder="e.g. 2031"
                      className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
                  </div>
                </div>
              </div>
            )}

            <div>
              <label className="text-xs text-text-secondary">Notes (optional)</label>
              <textarea value={memberForm.notes || ""}
                onChange={(e) => setMemberForm((f) => ({ ...f, notes: e.target.value || null }))}
                rows={2}
                className="w-full mt-1 text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20" />
            </div>

            <div className="flex gap-2">
              <button onClick={saveMember} disabled={memberSaving || !memberForm.name}
                className="flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-60">
                {memberSaving && <Loader2 size={14} className="animate-spin" />}
                {editMemberId ? "Update" : "Add"} Member
              </button>
              <button onClick={() => { setShowMemberForm(false); setEditMemberId(null); }} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancel</button>
            </div>
          </div>
        </Card>
      )}

      {milestones.length > 0 && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Family Milestones</h3>
          <div className="space-y-2">
            {milestones.slice(0, 10).map((m, i) => {
              const cat = MILESTONE_CATEGORY_COLOR[m.category] || "bg-surface text-text-secondary border-border";
              return (
                <div key={i} className={`p-3 rounded-xl border ${cat} flex items-start gap-3`}>
                  <div className="shrink-0 text-center">
                    <p className="text-lg font-bold leading-none">{m.years_away}</p>
                    <p className="text-xs uppercase tracking-wide opacity-70">yr{m.years_away !== 1 ? "s" : ""}</p>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold">{m.label}</p>
                    <p className="text-xs opacity-70 mt-0.5 line-clamp-2">{m.action}</p>
                  </div>
                  <span className="text-xs font-medium opacity-60 shrink-0">{m.target_year}</span>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </>
  );
}

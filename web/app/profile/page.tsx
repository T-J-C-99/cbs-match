"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppShellNav from "@/components/AppShellNav";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const GENDER_OPTIONS = ["man", "woman", "nonbinary", "other"] as const;

const PHOTO_FRAME_ASPECT = 4 / 5;

type GenderOption = typeof GENDER_OPTIONS[number];

type Profile = {
  display_name: string | null;
  cbs_year: string | null;
  hometown: string | null;
  phone_number?: string | null;
  instagram_handle?: string | null;
  photo_urls: string[];
  gender_identity?: string | null;
  seeking_genders?: string[];
};

type DraftProfile = {
  display_name: string;
  cbs_year: string;
  hometown: string;
  phone_number: string;
  instagram_handle: string;
  gender_identity: GenderOption | "";
  seeking_genders: GenderOption[];
  photo_urls: [string, string, string];
};

type VibeCard = {
  title?: string;
  three_bullets?: string[];
  one_watchout?: string;
  best_date_energy?: { key?: string; label?: string };
  opener_style?: { key?: string; template?: string };
  compatibility_motto?: string;
};

type PhotoEdit = {
  scale: number;
  offsetX: number;
  offsetY: number;
};

function ProfileInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requiredFlow = searchParams.get("required") === "1";
  const { fetchWithAuth } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [editorFile, setEditorFile] = useState<File | null>(null);
  const [editorPreviewUrl, setEditorPreviewUrl] = useState<string | null>(null);
  const [cropEdit, setCropEdit] = useState<PhotoEdit>({ scale: 1, offsetX: 0, offsetY: 0 });
  const [activePreviewPhoto, setActivePreviewPhoto] = useState(0);
  const [vibeCard, setVibeCard] = useState<VibeCard | null>(null);
  const [hasCompletedSurvey, setHasCompletedSurvey] = useState<boolean | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [slotAction, setSlotAction] = useState<{ mode: "add" | "replace"; index: number } | null>(null);
  const [draggedPhotoIndex, setDraggedPhotoIndex] = useState<number | null>(null);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const slotFileInputRef = useRef<HTMLInputElement | null>(null);
  const dragStartRef = useRef<{ startX: number; startY: number; baseOffsetX: number; baseOffsetY: number } | null>(null);

  const [draft, setDraft] = useState<DraftProfile>({
    display_name: "",
    cbs_year: "26",
    hometown: "",
    phone_number: "",
    instagram_handle: "",
    gender_identity: "",
    seeking_genders: [],
    photo_urls: ["", "", ""],
  });

  const hydrateDraftFromProfile = (p: Profile) => {
    const rawGender = String(p.gender_identity || "").toLowerCase();
    setDraft({
      display_name: String(p.display_name || ""),
      cbs_year: p.cbs_year === "27" ? "27" : "26",
      hometown: String(p.hometown || ""),
      phone_number: String(p.phone_number || ""),
      instagram_handle: String(p.instagram_handle || ""),
      gender_identity: GENDER_OPTIONS.includes(rawGender as GenderOption) ? (rawGender as GenderOption) : "",
      seeking_genders: (Array.isArray(p.seeking_genders) ? p.seeking_genders : [])
        .map((g) => String(g).toLowerCase())
        .filter((g): g is GenderOption => GENDER_OPTIONS.includes(g as GenderOption)),
      photo_urls: [p.photo_urls?.[0] || "", p.photo_urls?.[1] || "", p.photo_urls?.[2] || ""],
    });
  };

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileRes, stateRes] = await Promise.all([
        fetchWithAuth(`${API_BASE}/users/me/profile`),
        fetchWithAuth(`${API_BASE}/users/me/state`),
      ]);
      const profileData = await profileRes.json().catch(() => ({}));
      const stateData = await stateRes.json().catch(() => ({}));

      if (!profileRes.ok) throw new Error(profileData.detail || "Could not load profile");
      if (!stateRes.ok) throw new Error(stateData.detail || "Could not load state");

      const p: Profile = profileData.profile || {
        display_name: null,
        cbs_year: null,
        hometown: null,
        photo_urls: [],
        gender_identity: null,
        seeking_genders: [],
      };
      setProfile(p);
      hydrateDraftFromProfile(p);

      const missing = (stateData?.profile?.missing_fields as string[]) || [];
      setMissingFields(missing);
      setHasCompletedSurvey(Boolean(stateData?.onboarding?.has_completed_survey));
      if (requiredFlow && missing.length > 0) {
        setIsEditing(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activePhotoUrls = useMemo(
    () => draft.photo_urls.map((x) => x.trim()).filter(Boolean),
    [draft.photo_urls],
  );

  const previewPhotos = useMemo(() => {
    if (activePhotoUrls.length) return activePhotoUrls;
    return (profile?.photo_urls || []).map((x) => x.trim()).filter(Boolean);
  }, [activePhotoUrls, profile?.photo_urls]);

  useEffect(() => {
    if (activePreviewPhoto >= previewPhotos.length) {
      setActivePreviewPhoto(0);
    }
  }, [activePreviewPhoto, previewPhotos.length]);

  const previewPhoto = previewPhotos[activePreviewPhoto] || "";

  const [oceanScores, setOceanScores] = useState<{ openness: number; conscientiousness: number; extraversion: number; agreeableness: number; neuroticism: number } | null>(null);
  
  useEffect(() => {
    const fetchInsights = async () => {
      setInsightsLoading(true);
      setInsightsError(null);
      try {
        const res = await fetchWithAuth(`${API_BASE}/users/me/insights`);
        if (res.ok) {
          const data = await res.json();
          setOceanScores(data.ocean_scores || null);
          if (!data?.ocean_scores) {
            setInsightsError("Insights returned without OCEAN scores.");
          }
        } else {
          const data = await res.json().catch(() => ({}));
          setOceanScores(null);
          setInsightsError(`Insights request failed (${res.status}): ${data?.detail || "Unknown error"}`);
        }
      } catch (e) {
        setOceanScores(null);
        setInsightsError(e instanceof Error ? e.message : "Could not load insights");
      } finally {
        setInsightsLoading(false);
      }
    };
    if (profile) {
      fetchInsights();
    }
  }, [profile, fetchWithAuth]);

  useEffect(() => {
    const loadVibe = async () => {
      try {
        const res = await fetchWithAuth(`${API_BASE}/users/me/vibe-card`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setVibeCard(null);
          return;
        }
        setVibeCard((data?.vibe || null) as VibeCard | null);
      } catch {
        setVibeCard(null);
      }
    };
    if (profile) loadVibe();
  }, [profile, fetchWithAuth]);
  
  // OCEAN trait labels and descriptions
  const OCEAN_CONFIG = {
    openness: { label: "O", fullLabel: "Openness", description: "Curiosity, creativity, and openness to new experiences" },
    conscientiousness: { label: "C", fullLabel: "Conscientiousness", description: "Organization, dependability, and self-discipline" },
    extraversion: { label: "E", fullLabel: "Extraversion", description: "Social energy, assertiveness, and positive emotions" },
    agreeableness: { label: "A", fullLabel: "Agreeableness", description: "Cooperation, trust, and consideration for others" },
    neuroticism: { label: "N", fullLabel: "Neuroticism", description: "Emotional sensitivity and stress reactivity" },
  };
  
  function getScoreCategory(score: number): { label: string; color: string } {
    if (score >= 85) return { label: "Very High", color: "bg-emerald-500" };
    if (score >= 70) return { label: "High", color: "bg-emerald-400" };
    if (score >= 55) return { label: "Medium", color: "bg-slate-400" };
    if (score >= 40) return { label: "Low", color: "bg-slate-300" };
    return { label: "Very Low", color: "bg-slate-200" };
  }

  const toggleSeekingGender = (g: GenderOption) => {
    setDraft((prev) => ({
      ...prev,
      seeking_genders: prev.seeking_genders.includes(g)
        ? prev.seeking_genders.filter((x) => x !== g)
        : [...prev.seeking_genders, g],
    }));
  };

  const beginPhotoDrag = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!editorPreviewUrl) return;
    dragStartRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      baseOffsetX: cropEdit.offsetX,
      baseOffsetY: cropEdit.offsetY,
    };

    const onMove = (e: MouseEvent) => {
      const drag = dragStartRef.current;
      if (!drag) return;
      setCropEdit((prev) => ({
        ...prev,
        offsetX: drag.baseOffsetX + (e.clientX - drag.startX),
        offsetY: drag.baseOffsetY + (e.clientY - drag.startY),
      }));
    };

    const onUp = () => {
      dragStartRef.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const renderCroppedFile = async (file: File, edit: PhotoEdit): Promise<File> => {
    const imgUrl = URL.createObjectURL(file);
    try {
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const el = new Image();
        el.onload = () => resolve(el);
        el.onerror = () => reject(new Error("Could not read image"));
        el.src = imgUrl;
      });

      const frame = frameRef.current;
      const frameWidth = frame?.clientWidth || 320;
      const frameHeight = frame?.clientHeight || Math.round(frameWidth / PHOTO_FRAME_ASPECT);

      const baseScale = Math.max(frameWidth / img.naturalWidth, frameHeight / img.naturalHeight);
      const effectiveScale = Math.max(1, edit.scale) * baseScale;
      const renderedWidth = img.naturalWidth * effectiveScale;
      const renderedHeight = img.naturalHeight * effectiveScale;

      const imageLeft = (frameWidth - renderedWidth) / 2 + edit.offsetX;
      const imageTop = (frameHeight - renderedHeight) / 2 + edit.offsetY;

      let sx = (0 - imageLeft) / effectiveScale;
      let sy = (0 - imageTop) / effectiveScale;
      let sw = frameWidth / effectiveScale;
      let sh = frameHeight / effectiveScale;

      sx = Math.max(0, Math.min(img.naturalWidth - 1, sx));
      sy = Math.max(0, Math.min(img.naturalHeight - 1, sy));
      sw = Math.max(1, Math.min(img.naturalWidth - sx, sw));
      sh = Math.max(1, Math.min(img.naturalHeight - sy, sh));

      const outW = 800;
      const outH = Math.round(outW / PHOTO_FRAME_ASPECT);
      const canvas = document.createElement("canvas");
      canvas.width = outW;
      canvas.height = outH;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Could not process image");
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outW, outH);

      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not create cropped image"))), "image/jpeg", 0.92);
      });

      const baseName = file.name.replace(/\.[^.]+$/, "");
      return new File([blob], `${baseName}-framed.jpg`, { type: "image/jpeg" });
    } finally {
      URL.revokeObjectURL(imgUrl);
    }
  };

  const resetCropEditor = () => {
    if (editorPreviewUrl) URL.revokeObjectURL(editorPreviewUrl);
    setEditorFile(null);
    setEditorPreviewUrl(null);
    setCropEdit({ scale: 1, offsetX: 0, offsetY: 0 });
    setSlotAction(null);
  };

  const prepareCropEditor = (file: File, action: { mode: "add" | "replace"; index: number }) => {
    if (editorPreviewUrl) URL.revokeObjectURL(editorPreviewUrl);
    setError(null);
    setNotice(null);
    setSlotAction(action);
    setEditorFile(file);
    setEditorPreviewUrl(URL.createObjectURL(file));
    setCropEdit({ scale: 1, offsetX: 0, offsetY: 0 });
  };

  const fetchPhotoAsFile = async (url: string, index: number) => {
    const response = await fetchWithAuth(url);
    if (!response.ok) throw new Error("Could not open existing photo for editing");
    const blob = await response.blob();
    const type = blob.type || "image/jpeg";
    const extension = type.includes("png") ? "png" : type.includes("webp") ? "webp" : "jpg";
    return new File([blob], `photo-${index + 1}.${extension}`, { type });
  };

  const openSlotPicker = (index: number) => {
    const hasPhoto = Boolean(activePhotoUrls[index]);
    if (!hasPhoto && activePhotoUrls.length >= 3) {
      setError("You already have 3 photos. Remove one before adding another.");
      return;
    }

    if (hasPhoto) {
      const existingUrl = activePhotoUrls[index];
      if (!existingUrl) return;
      setUploadingPhotos(true);
      fetchPhotoAsFile(existingUrl, index)
        .then((file) => {
          prepareCropEditor(file, { mode: "replace", index });
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : "Could not open photo editor");
        })
        .finally(() => {
          setUploadingPhotos(false);
        });
      return;
    }

    setError(null);
    setNotice(null);
    setSlotAction({ mode: "add", index });
    slotFileInputRef.current?.click();
  };

  const removePhotoAt = (index: number) => {
    const next = activePhotoUrls.filter((_, idx) => idx !== index).slice(0, 3);
    setDraft((d) => ({ ...d, photo_urls: [next[0] || "", next[1] || "", next[2] || ""] }));
    setActivePreviewPhoto((prev) => Math.max(0, Math.min(prev, Math.max(0, next.length - 1))));
    setNotice("Photo removed. Click Save profile to apply changes.");
  };

  const handlePhotoDragStart = (e: React.DragEvent, index: number) => {
    if (!activePhotoUrls[index]) return;
    setDraggedPhotoIndex(index);
    e.dataTransfer.effectAllowed = "move";
  };

  const handlePhotoDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handlePhotoDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (draggedPhotoIndex === null || draggedPhotoIndex === dropIndex) {
      setDraggedPhotoIndex(null);
      return;
    }

    const reordered = [...draft.photo_urls];
    const [draggedUrl] = reordered.splice(draggedPhotoIndex, 1, "");
    
    if (reordered[dropIndex]) {
      reordered.splice(draggedPhotoIndex, 1, reordered[dropIndex]);
      reordered[dropIndex] = draggedUrl;
    } else {
      reordered[dropIndex] = draggedUrl;
    }

    setDraft((d) => ({ ...d, photo_urls: [reordered[0] || "", reordered[1] || "", reordered[2] || ""] }));
    setDraggedPhotoIndex(null);
    setNotice("Photos reordered. Click Save profile to apply changes.");
  };

  const handlePhotoDragEnd = () => {
    setDraggedPhotoIndex(null);
  };

  const onPhotoFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = Array.from(e.target.files || [])[0];
    e.target.value = "";
    if (!file) return;
    if (!slotAction) {
      setError("Pick a photo slot first.");
      return;
    }

    prepareCropEditor(file, slotAction);
  };

  useEffect(() => {
    return () => {
      if (editorPreviewUrl) URL.revokeObjectURL(editorPreviewUrl);
    };
  }, [editorPreviewUrl]);

  const uploadSelectedPhoto = async () => {
    setError(null);
    setNotice(null);
    if (!editorFile || !slotAction) {
      setError("Choose a photo first.");
      return;
    }

    setUploadingPhotos(true);
    try {
      const action = slotAction;
      const croppedFile = await renderCroppedFile(editorFile, cropEdit);
      const form = new FormData();
      form.append("photos", croppedFile);
      if (action?.mode === "replace") {
        form.append("replace_index", String(action.index));
      }
      const res = await fetchWithAuth(`${API_BASE}/users/me/profile/photos`, {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not upload photos");

      const urls = Array.isArray(data?.photo_urls)
        ? data.photo_urls.map((v: unknown) => String(v || "").trim()).filter(Boolean).slice(0, 3)
        : [];
      if (!urls.length) throw new Error("Upload succeeded but no photo URLs were returned");

      setDraft((d) => ({ ...d, photo_urls: [urls[0] || "", urls[1] || "", urls[2] || ""] }));
      resetCropEditor();
      if (action?.mode === "replace") {
        setNotice(`Photo ${action.index + 1} updated and saved.`);
      } else {
        setNotice(`Photo added and saved (${urls.length}/3 on profile).`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not upload photos");
    } finally {
      setUploadingPhotos(false);
    }
  };

  const saveProfile = async () => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetchWithAuth(`${API_BASE}/users/me/profile`, {
        method: "PUT",
        body: JSON.stringify({
          display_name: draft.display_name.trim(),
          cbs_year: draft.cbs_year,
          hometown: draft.hometown.trim(),
          phone_number: draft.phone_number.trim() || null,
          instagram_handle: draft.instagram_handle.trim() || null,
          gender_identity: draft.gender_identity || null,
          seeking_genders: draft.seeking_genders,
          photo_urls: activePhotoUrls,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not save profile");

      const savedProfile = (data?.profile || null) as Profile | null;
      if (savedProfile) {
        setProfile(savedProfile);
        hydrateDraftFromProfile(savedProfile);
      }

      const stateRes = await fetchWithAuth(`${API_BASE}/users/me/state`);
      const stateData = await stateRes.json().catch(() => ({}));
      if (!stateRes.ok) throw new Error(stateData.detail || "Profile saved but state refresh failed");

      const stillMissing = (stateData?.profile?.missing_fields as string[]) || [];
      setMissingFields(stillMissing);
      setHasCompletedSurvey(Boolean(stateData?.onboarding?.has_completed_survey));

      if (stillMissing.length === 0) {
        setNotice("Profile complete. You can now access all match features.");
        setIsEditing(false);
        if (requiredFlow) {
          router.push("/match");
          return;
        }
      } else {
        setNotice("Profile saved. Please complete all required fields to unlock matching.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setSaving(false);
    }
  };

  const requiredLabels: Record<string, string> = {
    display_name: "Display name",
    cbs_year: "CBS year",
    hometown: "Hometown",
    gender_identity: "Gender",
    seeking_genders: "Who you want to match with",
    photo_urls: "At least 1 photo",
  };

  return (
    <div className="cbs-page-shell">
      <AppShellNav />

      <h1 className="text-3xl font-semibold text-cbs-ink">Your profile</h1>
      <p className="mt-2 text-sm text-cbs-slate">Preview your card first, then edit when you’re ready.</p>
      {loading && <p className="mt-2 text-xs text-cbs-slate">Syncing profile…</p>}

      {requiredFlow && missingFields.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">Profile completion required before continuing</p>
          <p className="mt-1">Missing: {missingFields.map((k) => requiredLabels[k] || k).join(", ")}</p>
        </div>
      )}

      {error && <p className="mt-4 rounded bg-red-100 px-3 py-2 text-sm text-red-700">{error}</p>}
      {notice && <p className="mt-4 rounded bg-emerald-100 px-3 py-2 text-sm text-emerald-800">{notice}</p>}

      <div className="mx-auto mt-6 w-full max-w-5xl space-y-4 rounded-xl border border-cbs-columbia bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-6">
          <div className="rounded-xl border border-cbs-columbia/50 p-4 lg:max-w-[390px] lg:justify-self-start">
            <p className="text-sm text-cbs-slate">Profile preview</p>
            <div className="mx-auto mt-3 lg:max-w-[340px]">
              <div className="relative">
                {previewPhoto ? (
                  <img src={previewPhoto} alt={`Profile preview ${activePreviewPhoto + 1}`} className="aspect-[4/5] w-full rounded-xl object-cover" />
                ) : (
                  <div className="flex aspect-[4/5] w-full items-center justify-center rounded-xl bg-slate-100 text-slate-500">No photo yet</div>
                )}

                {previewPhotos.length > 1 && (
                  <>
                    <button
                      type="button"
                      onClick={() => setActivePreviewPhoto((i) => (i === 0 ? previewPhotos.length - 1 : i - 1))}
                      className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-white/85 px-3 py-2 text-sm font-semibold text-cbs-ink shadow"
                      aria-label="Previous profile photo"
                    >
                      ‹
                    </button>
                    <button
                      type="button"
                      onClick={() => setActivePreviewPhoto((i) => (i === previewPhotos.length - 1 ? 0 : i + 1))}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-white/85 px-3 py-2 text-sm font-semibold text-cbs-ink shadow"
                      aria-label="Next profile photo"
                    >
                      ›
                    </button>
                  </>
                )}
              </div>

              {previewPhotos.length > 1 && (
                <div className="mt-2 flex justify-center gap-1.5">
                  {previewPhotos.map((_, idx) => (
                    <button
                      key={`preview-dot-${idx}`}
                      type="button"
                      onClick={() => setActivePreviewPhoto(idx)}
                      className={`h-2.5 w-2.5 rounded-full ${idx === activePreviewPhoto ? "bg-cbs-navy" : "bg-slate-300"}`}
                      aria-label={`View profile photo ${idx + 1}`}
                    />
                  ))}
                </div>
              )}
            </div>
            <h2 className="mt-4 text-2xl font-bold text-cbs-ink">{profile?.display_name || draft.display_name || "Your name"}</h2>
            <p className="mt-1 text-cbs-slate">CBS {profile?.cbs_year || draft.cbs_year || "—"}{(profile?.hometown || draft.hometown) ? ` • ${profile?.hometown || draft.hometown}` : ""}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cbs-slate">Insights from the Dean</p>
            
            {/* OCEAN Cards */}
            {oceanScores ? (
              <div className="mt-3 flex gap-2">
                {(Object.keys(OCEAN_CONFIG) as Array<keyof typeof OCEAN_CONFIG>).map((trait) => {
                  const config = OCEAN_CONFIG[trait];
                  const score = oceanScores[trait];
                  const category = getScoreCategory(score);
                  return (
                    <div
                      key={trait}
                      className="group relative flex-1 rounded-lg border border-slate-200 bg-white p-2 text-center transition-shadow hover:shadow-md"
                      title={`${config.fullLabel}: ${config.description}`}
                    >
                      <div className="text-lg font-bold text-cbs-ink">{config.label}</div>
                      <div className={`mt-1 h-2 w-full rounded-full ${category.color}`} />
                      <div className="mt-1 text-[10px] font-medium text-slate-500">{category.label}</div>
                      {/* Tooltip on hover */}
                      <div className="pointer-events-none absolute -bottom-16 left-1/2 z-10 hidden w-36 -translate-x-1/2 rounded bg-cbs-ink px-2 py-1.5 text-[10px] leading-tight text-white opacity-0 shadow-lg transition-opacity group-hover:block group-hover:opacity-100">
                        <div className="font-semibold">{config.fullLabel}</div>
                        <div className="mt-0.5 text-white/80">{config.description}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                {insightsLoading
                  ? "Loading OCEAN insights…"
                  : hasCompletedSurvey === false
                    ? "Survey not completed yet. Complete your survey to generate OCEAN scores and insights."
                    : insightsError || "No OCEAN scores available yet."}
                {(hasCompletedSurvey === false || insightsError) && (
                  <div className="mt-2 flex gap-2">
                    {hasCompletedSurvey === false && (
                      <button
                        type="button"
                        onClick={() => router.push("/welcome")}
                        className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold text-amber-900"
                      >
                        Go to survey
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setProfile((prev) => (prev ? { ...prev } : prev));
                      }}
                      className="rounded border border-amber-300 bg-white px-2 py-1 font-semibold text-amber-900"
                    >
                      Retry insights
                    </button>
                  </div>
                )}
              </div>
            )}
            
            {/* Vibe card content moved directly under OCEAN cards */}
            {vibeCard ? (
              <div className="mt-4 rounded-lg border border-cbs-columbia bg-white p-4">
                <h3 className="text-base font-semibold text-cbs-ink">{vibeCard.title || "Your dating profile"}</h3>
                <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
                  {(vibeCard.three_bullets || []).slice(0, 3).map((line) => (
                    <li key={line}>• {line}</li>
                  ))}
                </ul>
                {vibeCard.one_watchout ? <p className="mt-2 text-sm text-slate-700"><span className="font-medium text-cbs-ink">Watchout:</span> {vibeCard.one_watchout}</p> : null}
                {vibeCard.best_date_energy?.label ? (
                  <p className="mt-1 text-sm text-slate-700"><span className="font-medium text-cbs-ink">Best date energy:</span> {vibeCard.best_date_energy.label}</p>
                ) : null}
                {vibeCard.opener_style?.template ? (
                  <p className="mt-1 text-sm text-slate-700"><span className="font-medium text-cbs-ink">Opener style:</span> {vibeCard.opener_style.template}</p>
                ) : null}
                {vibeCard.compatibility_motto ? <p className="mt-2 text-sm text-cbs-slate">{vibeCard.compatibility_motto}</p> : null}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-600">Complete your survey to generate your vibe card.</p>
            )}
          </div>
        </div>

        {!isEditing ? (
          <button onClick={() => setIsEditing(true)} className="rounded-lg bg-cbs-navy px-4 py-2 text-sm font-semibold text-white">
            Edit profile
          </button>
        ) : (
          <>
            <div>
              <label className="mb-1 block text-sm font-medium text-cbs-ink">Display name *</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={draft.display_name} onChange={(e) => setDraft((d) => ({ ...d, display_name: e.target.value }))} placeholder="How others will see your name" />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-cbs-ink">CBS Year *</label>
              <select className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={draft.cbs_year} onChange={(e) => setDraft((d) => ({ ...d, cbs_year: e.target.value }))}>
                <option value="26">26</option>
                <option value="27">27</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-cbs-ink">Hometown *</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={draft.hometown} onChange={(e) => setDraft((d) => ({ ...d, hometown: e.target.value }))} placeholder="e.g., New York, NY" />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-cbs-ink">Phone number</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={draft.phone_number} onChange={(e) => setDraft((d) => ({ ...d, phone_number: e.target.value }))} placeholder="e.g., +1 212 555 0123" />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-cbs-ink">Instagram handle</label>
              <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={draft.instagram_handle} onChange={(e) => setDraft((d) => ({ ...d, instagram_handle: e.target.value.replace(/^@+/, "") }))} placeholder="e.g., your_handle" />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-cbs-ink">Gender *</label>
              <div className="flex flex-wrap gap-2">
                {GENDER_OPTIONS.map((g) => {
                  const active = draft.gender_identity === g;
                  return (
                    <button key={g} type="button" onClick={() => setDraft((d) => ({ ...d, gender_identity: active ? "" : g }))} className={`rounded-full border px-3 py-1.5 text-sm ${active ? "border-cbs-navy bg-cbs-navy text-white" : "border-slate-300 bg-white text-slate-700"}`}>
                      {g}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-cbs-ink">Looking for *</label>
              <div className="flex flex-wrap gap-2">
                {GENDER_OPTIONS.map((g) => {
                  const active = draft.seeking_genders.includes(g);
                  return (
                    <button key={g} type="button" onClick={() => toggleSeekingGender(g)} className={`rounded-full border px-3 py-1.5 text-sm ${active ? "border-cbs-navy bg-cbs-navy text-white" : "border-slate-300 bg-white text-slate-700"}`}>
                      {g}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 p-4">
              <label className="mb-2 block text-sm font-medium text-cbs-ink">Photos *</label>
              <p className="mb-3 text-xs text-cbs-slate">Use the 3 slots below. Click an empty slot to add a photo. Click a filled slot to edit, or Remove to delete. Drag photos between slots to reorder.</p>
              <div className="grid grid-cols-3 gap-3">
                {[0, 1, 2].map((idx) => {
                  const url = activePhotoUrls[idx] || "";
                  return (
                    <div key={`slot-${idx}`} className="space-y-2">
                      <button
                        type="button"
                        onClick={() => openSlotPicker(idx)}
                        draggable={!!url}
                        onDragStart={(e) => handlePhotoDragStart(e, idx)}
                        onDragOver={(e) => handlePhotoDragOver(e, idx)}
                        onDrop={(e) => handlePhotoDrop(e, idx)}
                        onDragEnd={handlePhotoDragEnd}
                        className={`relative flex aspect-[4/5] w-full items-center justify-center overflow-hidden rounded-lg border border-slate-300 bg-slate-50 text-slate-500 hover:bg-slate-100 transition-opacity ${
                          draggedPhotoIndex === idx ? "opacity-50" : ""
                        } ${url ? "cursor-grab active:cursor-grabbing" : ""}`}
                      >
                        {url ? (
                          <img src={url} alt={`Photo slot ${idx + 1}`} className="h-full w-full object-cover pointer-events-none" />
                        ) : (
                          <span className="text-2xl font-semibold">+</span>
                        )}
                        <span className="absolute bottom-1 right-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white">{idx + 1}</span>
                      </button>
                      {url && (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => openSlotPicker(idx)}
                            className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 whitespace-nowrap"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => removePhotoAt(idx)}
                            className="flex-1 rounded border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 whitespace-nowrap"
                          >
                            Remove
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <input
                ref={slotFileInputRef}
                type="file"
                accept="image/jpeg,image/jpg,image/png,image/webp"
                onChange={onPhotoFileChange}
                className="hidden"
              />

              {editorPreviewUrl && slotAction && (
                <div className="mt-4 rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-cbs-slate">Frame your photo exactly how it appears on cards: drag to reposition, zoom to resize.</p>
                  <p className="mt-2 text-xs text-cbs-slate">
                    Editing photo slot {slotAction.index + 1}
                  </p>
                  <div
                    ref={frameRef}
                    onMouseDown={beginPhotoDrag}
                    className="relative mt-3 aspect-[4/5] w-full max-w-xs cursor-move overflow-hidden rounded-xl border border-cbs-columbia bg-slate-100"
                  >
                    <img
                      src={editorPreviewUrl}
                      alt={`Crop preview ${slotAction.index + 1}`}
                      draggable={false}
                      className="pointer-events-none absolute inset-0 h-full w-full select-none object-cover"
                      style={{
                        transform: `translate(${cropEdit.offsetX}px, ${cropEdit.offsetY}px) scale(${cropEdit.scale})`,
                        transformOrigin: "center center",
                      }}
                    />
                  </div>
                  <label className="mt-3 block text-xs font-medium text-cbs-ink">Zoom</label>
                  <input
                    type="range"
                    min={1}
                    max={2.2}
                    step={0.01}
                    value={cropEdit.scale}
                    onChange={(e) => setCropEdit((prev) => ({ ...prev, scale: Number(e.target.value) }))}
                    className="mt-1 w-full max-w-xs"
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={uploadSelectedPhoto}
                      disabled={uploadingPhotos || !editorFile}
                      className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                    >
                      {uploadingPhotos ? "Saving photo..." : slotAction.mode === "replace" ? "Save edited photo" : "Add photo"}
                    </button>
                    <button
                      type="button"
                      onClick={resetCropEditor}
                      disabled={uploadingPhotos}
                      className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button onClick={saveProfile} disabled={saving} className="rounded-lg bg-cbs-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                {saving ? "Saving..." : "Save profile"}
              </button>
              <button onClick={() => setIsEditing(false)} type="button" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <RequireAuth requireVerified>
      <ProfileInner />
    </RequireAuth>
  );
}

import React, { useEffect, useMemo, useState, useRef } from "react";
import { Alert, Pressable, ScrollView, Text, TextInput, View, Image, Animated, PanResponder, ActionSheetIOS, Platform } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { api } from "../api/endpoints";
import { colors } from "../theme/colors";
import { SafeAreaView } from "react-native-safe-area-context";

const GENDER_OPTIONS = [
  { label: "Man", value: "man" },
  { label: "Woman", value: "woman" },
  { label: "Non-binary", value: "nonbinary" },
  { label: "Other", value: "other" }
];

const FieldLabel = ({ children }: { children: React.ReactNode }) => (
  <Text style={{ color: colors.mutedText, fontSize: 12, marginTop: 2 }}>{children}</Text>
);

export default function ProfileScreen() {
  const [profile, setProfile] = useState<any>(null);
  const [vibeCard, setVibeCard] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadingSlot, setUploadingSlot] = useState<number | null>(null);
  const [previewPhotoIdx, setPreviewPhotoIdx] = useState(0);
  const [draft, setDraft] = useState({
    display_name: "",
    cbs_year: "26",
    hometown: "",
    phone_number: "",
    instagram_handle: "",
    gender_identity: "",
    seeking_genders: [] as string[],
    photo_urls: ["", "", ""] as string[]
  });

  useEffect(() => {
    (async () => {
      try {
        const [p, vibe] = await Promise.all([
          api.getProfile(),
          api.getVibeCard().catch(() => null),
        ]);
        setProfile(p.profile);
        setVibeCard((vibe as any)?.vibe || null);
        setDraft({
          display_name: p.profile.display_name || "",
          cbs_year: p.profile.cbs_year || "26",
          hometown: p.profile.hometown || "",
          phone_number: p.profile.phone_number || "",
          instagram_handle: p.profile.instagram_handle || "",
          gender_identity: p.profile.gender_identity || "",
          seeking_genders: p.profile.seeking_genders || [],
          photo_urls: [p.profile.photo_urls?.[0] || "", p.profile.photo_urls?.[1] || "", p.profile.photo_urls?.[2] || ""]
        });
      } catch (e) {
        Alert.alert("Profile load failed", e instanceof Error ? e.message : "Could not load profile");
      }
    })();
  }, []);

  const activePhotoUrls = useMemo(() => draft.photo_urls.map((u) => String(u || "").trim()).filter(Boolean), [draft.photo_urls]);
  const previewPhotos = useMemo(() => {
    if (activePhotoUrls.length) return activePhotoUrls;
    return (profile?.photo_urls || []).filter(Boolean);
  }, [activePhotoUrls, profile]);

  useEffect(() => {
    if (!previewPhotos.length) {
      setPreviewPhotoIdx(0);
      return;
    }
    setPreviewPhotoIdx((n) => Math.max(0, Math.min(n, previewPhotos.length - 1)));
  }, [previewPhotos]);

  const setPhotoUrls = (urls: string[]) => {
    const next = [urls[0] || "", urls[1] || "", urls[2] || ""];
    setDraft((d) => ({ ...d, photo_urls: next }));
    setProfile((p: any) => (p ? { ...p, photo_urls: next.filter(Boolean) } : p));
  };

  const pickAndUploadPhoto = async (index: number, mode: "add" | "replace") => {
    try {
      if (mode === "add" && activePhotoUrls.length >= 3) {
        Alert.alert("Photo limit", "You already have 3 photos. Remove one before adding another.");
        return;
      }

      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission needed", "Please allow photo library access to add profile photos.");
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"] as any,
        allowsEditing: true,
        aspect: [4, 5],
        quality: 0.92
      });

      if (result.canceled || !result.assets?.length) return;

      const asset = result.assets[0];
      const uri = asset.uri;
      if (!uri) return;

      const fileName = asset.fileName || `photo-${index + 1}.jpg`;
      const type = asset.mimeType || "image/jpeg";

      const form = new FormData();
      form.append("photos", { uri, name: fileName, type } as any);
      if (mode === "replace") {
        form.append("replace_index", String(index));
      }

      setUploadingSlot(index);
      try {
        const data = await api.uploadProfilePhoto(form);
        const urls = Array.isArray(data.photo_urls)
          ? data.photo_urls.map((v) => String(v || "").trim()).filter(Boolean).slice(0, 3)
          : [];
        if (!urls.length) throw new Error("Upload succeeded but no photo URLs returned");
        setPhotoUrls(urls);
        Alert.alert("Saved", mode === "replace" ? `Photo ${index + 1} updated.` : "Photo added.");
      } catch (e) {
        Alert.alert("Upload failed", e instanceof Error ? e.message : "Could not upload photo");
      } finally {
        setUploadingSlot(null);
      }
    } catch (e) {
      Alert.alert("Photo editor error", e instanceof Error ? e.message : "Could not open photo picker");
      setUploadingSlot(null);
    }
  };

  const removePhotoAt = (index: number) => {
    const next = activePhotoUrls.filter((_, i) => i !== index).slice(0, 3);
    setPhotoUrls(next);
  };

  const movePhotoLeft = (index: number) => {
    if (index === 0) return;
    const reordered = [...draft.photo_urls];
    [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]];
    setDraft((d) => ({ ...d, photo_urls: [reordered[0] || "", reordered[1] || "", reordered[2] || ""] }));
  };

  const movePhotoRight = (index: number) => {
    if (index === 2) return;
    const reordered = [...draft.photo_urls];
    [reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]];
    setDraft((d) => ({ ...d, photo_urls: [reordered[0] || "", reordered[1] || "", reordered[2] || ""] }));
  };

  const handlePhotoLongPress = (index: number) => {
    const url = activePhotoUrls[index];
    if (!url) return;

    const canMoveLeft = index > 0;
    const canMoveRight = index < activePhotoUrls.length - 1;

    if (Platform.OS === "ios") {
      const options = ["Cancel", "Replace Photo"];
      const actions: (() => void)[] = [() => {}, () => pickAndUploadPhoto(index, "replace")];
      
      if (canMoveLeft) {
        options.push("Move Left");
        actions.push(() => movePhotoLeft(index));
      }
      if (canMoveRight) {
        options.push("Move Right");
        actions.push(() => movePhotoRight(index));
      }
      
      options.push("Remove Photo");
      actions.push(() => {
        Alert.alert(
          "Remove Photo",
          `Remove photo ${index + 1}?`,
          [
            { text: "Cancel", style: "cancel" },
            { text: "Remove", style: "destructive", onPress: () => removePhotoAt(index) },
          ]
        );
      });

      ActionSheetIOS.showActionSheetWithOptions(
        {
          options,
          destructiveButtonIndex: options.length - 1,
          cancelButtonIndex: 0,
        },
        (buttonIndex) => {
          if (buttonIndex > 0 && buttonIndex < actions.length) {
            actions[buttonIndex]();
          }
        }
      );
    } else {
      const buttons: any[] = [{ text: "Cancel", style: "cancel" }];
      
      buttons.push({ text: "Replace Photo", onPress: () => pickAndUploadPhoto(index, "replace") });
      
      if (canMoveLeft) {
        buttons.push({ text: "Move Left", onPress: () => movePhotoLeft(index) });
      }
      if (canMoveRight) {
        buttons.push({ text: "Move Right", onPress: () => movePhotoRight(index) });
      }
      
      buttons.push({ text: "Remove Photo", style: "destructive", onPress: () => removePhotoAt(index) });

      Alert.alert("Photo Options", `Choose an action for photo ${index + 1}`, buttons);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateProfile({
        display_name: draft.display_name,
        cbs_year: draft.cbs_year,
        hometown: draft.hometown,
        phone_number: draft.phone_number || null,
        instagram_handle: draft.instagram_handle || null,
        gender_identity: draft.gender_identity || null,
        seeking_genders: draft.seeking_genders,
        photo_urls: draft.photo_urls.filter(Boolean),
      });
      setProfile(updated.profile);
      setDraft((d) => ({ ...d, photo_urls: [updated.profile.photo_urls?.[0] || "", updated.profile.photo_urls?.[1] || "", updated.profile.photo_urls?.[2] || ""] }));
      setIsEditing(false);
      Alert.alert("Saved", "Profile updated");
    } catch (e) {
      Alert.alert("Error", e instanceof Error ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top"]}>
      <ScrollView style={{ flex: 1, backgroundColor: colors.background }} contentContainerStyle={{ padding: 16, gap: 12 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: colors.text }}>Profile</Text>
        <View style={{ borderWidth: 1, borderColor: colors.border, backgroundColor: "white", borderRadius: 16, padding: 14, gap: 8 }}>
          <Text style={{ color: colors.mutedText }}>Preview how you appear</Text>
          {!!previewPhotos.length ? (
            <View style={{ position: "relative" }}>
              <Image source={{ uri: previewPhotos[previewPhotoIdx] }} style={{ width: "100%", aspectRatio: 4 / 5, borderRadius: 12 }} resizeMode="cover" />
              {previewPhotos.length > 1 ? (
                <>
                  <Pressable
                    onPress={() => setPreviewPhotoIdx((n) => (n - 1 + previewPhotos.length) % previewPhotos.length)}
                    style={{ position: "absolute", left: 10, top: "50%", marginTop: -16, backgroundColor: "rgba(0,0,0,0.35)", borderRadius: 18, width: 32, height: 32, alignItems: "center", justifyContent: "center" }}
                  >
                    <Text style={{ color: "white", fontSize: 18, marginTop: -2 }}>‹</Text>
                  </Pressable>
                  <Pressable
                    onPress={() => setPreviewPhotoIdx((n) => (n + 1) % previewPhotos.length)}
                    style={{ position: "absolute", right: 10, top: "50%", marginTop: -16, backgroundColor: "rgba(0,0,0,0.35)", borderRadius: 18, width: 32, height: 32, alignItems: "center", justifyContent: "center" }}
                  >
                    <Text style={{ color: "white", fontSize: 18, marginTop: -2 }}>›</Text>
                  </Pressable>
                  <View style={{ position: "absolute", bottom: 8, left: 0, right: 0, flexDirection: "row", justifyContent: "center", gap: 6 }}>
                    {previewPhotos.map((_: string, i: number) => (
                      <View key={`preview-dot-${i}`} style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: i === previewPhotoIdx ? "white" : "rgba(255,255,255,0.5)" }} />
                    ))}
                  </View>
                </>
              ) : null}
            </View>
          ) : null}
          <Text style={{ fontSize: 24, fontWeight: "800", color: colors.text }}>{profile?.display_name || "Your name"}</Text>
          <Text style={{ color: colors.mutedText }}>CBS {profile?.cbs_year || "—"}{profile?.hometown ? ` • ${profile.hometown}` : ""}</Text>
        </View>

        <View style={{ borderWidth: 1, borderColor: colors.border, backgroundColor: "white", borderRadius: 16, padding: 14, gap: 8 }}>
          <Text style={{ color: colors.mutedText }}>Your vibe card</Text>
          {vibeCard ? (
            <>
              <Text style={{ fontSize: 20, fontWeight: "800", color: colors.text }}>{vibeCard.title || "Your dating profile"}</Text>
              {(vibeCard.three_bullets || []).slice(0, 3).map((line: string) => (
                <Text key={line} style={{ color: colors.text }}>• {line}</Text>
              ))}
              {vibeCard.one_watchout ? (
                <Text style={{ color: colors.mutedText }}><Text style={{ fontWeight: "700", color: colors.text }}>Watchout:</Text> {vibeCard.one_watchout}</Text>
              ) : null}
              {vibeCard.best_date_energy?.label ? (
                <Text style={{ color: colors.mutedText }}><Text style={{ fontWeight: "700", color: colors.text }}>Best date energy:</Text> {vibeCard.best_date_energy.label}</Text>
              ) : null}
            </>
          ) : (
            <Text style={{ color: colors.mutedText }}>Complete your survey to generate your vibe card.</Text>
          )}
        </View>

        {!isEditing ? (
          <Pressable onPress={() => setIsEditing(true)} style={{ backgroundColor: colors.primary, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", color: "white", fontWeight: "700" }}>Edit profile</Text></Pressable>
        ) : (
          <View style={{ borderWidth: 1, borderColor: colors.border, backgroundColor: "white", borderRadius: 16, padding: 14, gap: 8 }}>
            <FieldLabel>Display name</FieldLabel>
            <TextInput value={draft.display_name} onChangeText={(v) => setDraft((d) => ({ ...d, display_name: v }))} placeholder="Display name" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }} />
            <FieldLabel>CBS Year</FieldLabel>
            <View style={{ flexDirection: "row", gap: 8 }}>
              {(["26", "27"] as const).map((year) => {
                const selected = draft.cbs_year === year;
                return (
                  <Pressable key={year} onPress={() => setDraft((d) => ({ ...d, cbs_year: year }))} style={{ flex: 1, borderWidth: 1, borderColor: selected ? colors.primary : colors.border, backgroundColor: selected ? "#e7eefb" : "white", borderRadius: 10, padding: 10 }}>
                    <Text style={{ textAlign: "center", color: selected ? colors.primary : colors.text, fontWeight: "700" }}>{year}</Text>
                  </Pressable>
                );
              })}
            </View>
            <FieldLabel>Hometown</FieldLabel>
            <TextInput value={draft.hometown} onChangeText={(v) => setDraft((d) => ({ ...d, hometown: v }))} placeholder="Hometown" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }} />
            <FieldLabel>Phone number</FieldLabel>
            <TextInput value={draft.phone_number} onChangeText={(v) => setDraft((d) => ({ ...d, phone_number: v }))} placeholder="Phone number" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }} />
            <FieldLabel>Instagram handle</FieldLabel>
            <TextInput value={draft.instagram_handle} onChangeText={(v) => setDraft((d) => ({ ...d, instagram_handle: v }))} placeholder="Instagram handle" autoCapitalize="none" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }} />

            <FieldLabel>Gender</FieldLabel>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              {GENDER_OPTIONS.map((option) => {
                const selected = draft.gender_identity === option.value;
                return (
                  <Pressable key={option.value} onPress={() => setDraft((d) => ({ ...d, gender_identity: selected ? "" : option.value }))} style={{ borderWidth: 1, borderColor: selected ? colors.primary : colors.border, backgroundColor: selected ? "#e7eefb" : "white", borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8 }}>
                    <Text style={{ color: selected ? colors.primary : colors.text, fontWeight: "600" }}>{option.label}</Text>
                  </Pressable>
                );
              })}
            </View>

            <FieldLabel>Seeking</FieldLabel>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              {GENDER_OPTIONS.map((option) => {
                const selected = draft.seeking_genders.includes(option.value);
                return (
                  <Pressable
                    key={`seeking-${option.value}`}
                    onPress={() => setDraft((d) => ({ ...d, seeking_genders: selected ? d.seeking_genders.filter((g) => g !== option.value) : [...d.seeking_genders, option.value] }))}
                    style={{ borderWidth: 1, borderColor: selected ? colors.primary : colors.border, backgroundColor: selected ? "#e7eefb" : "white", borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8 }}
                  >
                    <Text style={{ color: selected ? colors.primary : colors.text, fontWeight: "600" }}>{option.label}</Text>
                  </Pressable>
                );
              })}
            </View>

            <FieldLabel>Photos</FieldLabel>
            <Text style={{ color: colors.mutedText, fontSize: 12 }}>Tap + to add a photo or tap an existing photo to replace/crop. Long press a photo for more options. Up to 3 photos.</Text>
            <View style={{ flexDirection: "row", gap: 8 }}>
              {[0, 1, 2].map((idx) => {
                const url = activePhotoUrls[idx] || "";
                return (
                  <View key={`slot-${idx}`} style={{ flex: 1 }}>
                    <Pressable
                      onPress={() => (url ? pickAndUploadPhoto(idx, "replace") : pickAndUploadPhoto(idx, "add"))}
                      onLongPress={() => url ? handlePhotoLongPress(idx) : null}
                      disabled={uploadingSlot !== null}
                      style={{
                        borderWidth: 1,
                        borderColor: colors.border,
                        borderRadius: 10,
                        overflow: "hidden",
                        aspectRatio: 4 / 5,
                        alignItems: "center",
                        justifyContent: "center",
                        backgroundColor: "#f7f8fa",
                        opacity: uploadingSlot !== null ? 0.7 : 1,
                      }}
                    >
                      {url ? (
                        <Image source={{ uri: url }} style={{ width: "100%", height: "100%" }} resizeMode="cover" />
                      ) : (
                        <Text style={{ fontSize: 24, fontWeight: "700", color: colors.mutedText }}>+</Text>
                      )}
                      <View style={{ position: "absolute", bottom: 4, right: 4, backgroundColor: "rgba(0,0,0,0.6)", borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 }}>
                        <Text style={{ color: "white", fontSize: 10, fontWeight: "700" }}>{idx + 1}</Text>
                      </View>
                      {uploadingSlot === idx && (
                        <View style={{ position: "absolute", inset: 0, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center" }}>
                          <Text style={{ color: "white", fontSize: 12, fontWeight: "700" }}>Uploading...</Text>
                        </View>
                      )}
                    </Pressable>
                  </View>
                );
              })}
            </View>

            <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
              <Pressable disabled={saving} onPress={save} style={{ flex: 1, backgroundColor: colors.primary, borderRadius: 12, padding: 12, opacity: saving ? 0.7 : 1 }}><Text style={{ textAlign: "center", color: "white", fontWeight: "700" }}>{saving ? "Saving..." : "Save"}</Text></Pressable>
              <Pressable disabled={saving || uploadingSlot !== null} onPress={() => setIsEditing(false)} style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, opacity: saving ? 0.7 : 1 }}><Text style={{ textAlign: "center", fontWeight: "700" }}>Cancel</Text></Pressable>
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

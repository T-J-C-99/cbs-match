import React, { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { useAppStore } from "../store/appStore";
import { removeSecureItem, STORAGE_KEYS } from "../utils/storage";
import { colors } from "../theme/colors";
import { SafeAreaView } from "react-native-safe-area-context";

export default function SettingsScreen() {
  const qc = useQueryClient();
  const setUserId = useAppStore((s) => s.setUserId);
  const setUserEmail = useAppStore((s) => s.setUserEmail);
  const setIsEmailVerified = useAppStore((s) => s.setIsEmailVerified);
  const setAccessToken = useAppStore((s) => s.setAccessToken);
  const setRefreshToken = useAppStore((s) => s.setRefreshToken);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const setUsername = useAppStore((s) => s.setUsername);
  const setTenantSlug = useAppStore((s) => s.setTenantSlug);

  const [pauseMatches, setPauseMatches] = useState(false);
  const [notifPrefs, setNotifPrefs] = useState({
    email_enabled: true,
    push_enabled: false,
    quiet_hours_start_local: "",
    quiet_hours_end_local: "",
    timezone: "America/New_York",
  });
  const [notifSaving, setNotifSaving] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [blockIdentifier, setBlockIdentifier] = useState("");
  const [reportReason, setReportReason] = useState("");
  const [savingPause, setSavingPause] = useState(false);
  const [pauseStatus, setPauseStatus] = useState<string>("");
  const [blocking, setBlocking] = useState(false);
  const [vibeLoading, setVibeLoading] = useState(false);
  const [vibeSaving, setVibeSaving] = useState(false);
  const [vibeCard, setVibeCard] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    api.getPreferences().then((d) => setPauseMatches(!!d.preferences.pause_matches)).catch(() => undefined);
    api.getNotificationPreferences()
      .then((d: any) => {
        const p = d?.preferences || {};
        setNotifPrefs({
          email_enabled: !!p.email_enabled,
          push_enabled: !!p.push_enabled,
          quiet_hours_start_local: p.quiet_hours_start_local || "",
          quiet_hours_end_local: p.quiet_hours_end_local || "",
          timezone: p.timezone || "America/New_York",
        });
      })
      .catch(() => undefined);
  }, []);

  const saveNotificationPrefs = async () => {
    setNotifSaving(true);
    try {
      const data: any = await api.updateNotificationPreferences({
        email_enabled: !!notifPrefs.email_enabled,
        push_enabled: !!notifPrefs.push_enabled,
        quiet_hours_start_local: notifPrefs.quiet_hours_start_local || null,
        quiet_hours_end_local: notifPrefs.quiet_hours_end_local || null,
        timezone: notifPrefs.timezone || "America/New_York",
      });
      const p = data?.preferences || {};
      setNotifPrefs({
        email_enabled: !!p.email_enabled,
        push_enabled: !!p.push_enabled,
        quiet_hours_start_local: p.quiet_hours_start_local || "",
        quiet_hours_end_local: p.quiet_hours_end_local || "",
        timezone: p.timezone || "America/New_York",
      });
      Alert.alert("Saved", "Notification settings updated");
    } catch (e) {
      Alert.alert("Could not save", e instanceof Error ? e.message : "Try again");
    } finally {
      setNotifSaving(false);
    }
  };

  const clearLocalSession = async () => {
    setUserId(null); setUserEmail(null); setIsEmailVerified(false); setAccessToken(null); setRefreshToken(null); setSessionId(null); setUsername(null);
    await Promise.all([
      removeSecureItem(STORAGE_KEYS.userId), removeSecureItem(STORAGE_KEYS.userEmail), removeSecureItem(STORAGE_KEYS.isEmailVerified),
      removeSecureItem(STORAGE_KEYS.accessToken), removeSecureItem(STORAGE_KEYS.refreshToken), removeSecureItem(STORAGE_KEYS.sessionId),
      removeSecureItem(STORAGE_KEYS.lastSeenMatchKey),
    ]);
  };

  const logout = async () => {
    await clearLocalSession();
    Alert.alert("Logged out");
  };

  const changeCommunity = async () => {
    await clearLocalSession();
    setTenantSlug("cbs");
    await removeSecureItem(STORAGE_KEYS.tenantSlug);
    Alert.alert("Community cleared", "Choose a community on the next screen.");
  };

  const deleteAccount = () => {
    Alert.alert(
      "Delete account?",
      "This removes your public profile and match visibility.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Continue",
          style: "destructive",
          onPress: () => {
            Alert.alert(
              "Final confirmation",
              "This cannot be undone.",
              [
                { text: "Cancel", style: "cancel" },
                {
                  text: "Delete account",
                  style: "destructive",
                  onPress: async () => {
                    try {
                      await api.deleteAccount();
                      await clearLocalSession();
                      Alert.alert("Account deleted");
                    } catch (e) {
                      Alert.alert("Could not delete account", e instanceof Error ? e.message : "Please try again.");
                    }
                  },
                },
              ]
            );
          },
        },
      ]
    );
  };

  const updatePausePreference = async () => {
    const nextValue = !pauseMatches;
    const previousValue = pauseMatches;
    setPauseMatches(nextValue);
    setSavingPause(true);
    setPauseStatus("Saving...");
    try {
      await api.updatePreferences(nextValue);
      setPauseStatus(nextValue ? "Paused" : "Active");
    } catch (e) {
      setPauseMatches(previousValue);
      setPauseStatus("Could not save");
      Alert.alert("Error", e instanceof Error ? e.message : "Could not update match availability");
    } finally {
      setSavingPause(false);
    }
  };

  const loadVibeCard = async () => {
    setVibeLoading(true);
    try {
      const data: any = await api.getVibeCard();
      setVibeCard((data?.vibe_card as Record<string, any>) || (data?.vibe as Record<string, any>) || null);
    } catch (e) {
      Alert.alert("Vibe card unavailable", e instanceof Error ? e.message : "Complete your survey first.");
    } finally {
      setVibeLoading(false);
    }
  };

  const saveVibeCard = async () => {
    setVibeSaving(true);
    try {
      await api.saveVibeCard();
      Alert.alert("Saved", "Your current vibe card snapshot is saved.");
    } catch (e) {
      Alert.alert("Could not save", e instanceof Error ? e.message : "Try again.");
    } finally {
      setVibeSaving(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top"]}>
      <ScrollView style={{ flex: 1, backgroundColor: colors.background }} contentContainerStyle={{ padding: 16, gap: 12 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: colors.text }}>Settings</Text>

        <View style={{ backgroundColor: pauseMatches ? "#FFF7ED" : "white", borderRadius: 16, borderWidth: 1, borderColor: pauseMatches ? "#FDBA74" : colors.border, padding: 12, gap: 10 }}>
          <Text style={{ fontWeight: "800", color: colors.text }}>Weekly matching</Text>
          <Text style={{ color: colors.mutedText }}>
            {pauseMatches
              ? "Paused: you will not receive new pairings until you switch this off."
              : "Active: you are eligible for upcoming weekly pairings."}
          </Text>
          <Pressable
            onPress={updatePausePreference}
            disabled={savingPause}
            style={{
              marginTop: 2,
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
              borderWidth: 1,
              borderColor: pauseMatches ? "#FDBA74" : "#CBD5E1",
              backgroundColor: pauseMatches ? "#FFEDD5" : "#F8FAFC",
              borderRadius: 12,
              paddingHorizontal: 12,
              paddingVertical: 10,
              opacity: savingPause ? 0.7 : 1,
            }}
          >
            <Text style={{ color: colors.text, fontWeight: "600" }}>Pause new weekly matches</Text>
            <View
              style={{
                width: 44,
                height: 24,
                borderRadius: 999,
                backgroundColor: pauseMatches ? "#F59E0B" : "#94A3B8",
                padding: 2,
                justifyContent: "center",
              }}
            >
              <View
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 999,
                  backgroundColor: "white",
                  transform: [{ translateX: pauseMatches ? 20 : 0 }],
                }}
              />
            </View>
          </Pressable>
          {!!pauseStatus && pauseStatus !== "Paused" && pauseStatus !== "Active" ? (
            <Text style={{ color: pauseStatus === "Could not save" ? colors.danger : colors.mutedText, fontSize: 12 }}>{pauseStatus}</Text>
          ) : null}
        </View>

        <View style={{ backgroundColor: "white", borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }}>
          <Text style={{ fontWeight: "800", color: colors.text }}>Notifications</Text>
          <Text style={{ color: colors.mutedText }}>Choose delivery channels and optional quiet hours.</Text>

          <Pressable
            onPress={() => setNotifPrefs((p) => ({ ...p, email_enabled: !p.email_enabled }))}
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}
          >
            <Text style={{ fontWeight: "600", color: colors.text }}>Email notifications</Text>
            <Text style={{ color: notifPrefs.email_enabled ? colors.primary : colors.mutedText, fontWeight: "700" }}>{notifPrefs.email_enabled ? "ON" : "OFF"}</Text>
          </Pressable>

          <Pressable
            onPress={() => setNotifPrefs((p) => ({ ...p, push_enabled: !p.push_enabled }))}
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}
          >
            <Text style={{ fontWeight: "600", color: colors.text }}>Push notifications</Text>
            <Text style={{ color: notifPrefs.push_enabled ? colors.primary : colors.mutedText, fontWeight: "700" }}>{notifPrefs.push_enabled ? "ON" : "OFF"}</Text>
          </Pressable>

          <Text style={{ color: colors.mutedText, fontSize: 12 }}>Quiet hours start (HH:MM)</Text>
          <TextInput
            value={notifPrefs.quiet_hours_start_local}
            onChangeText={(v) => setNotifPrefs((p) => ({ ...p, quiet_hours_start_local: v }))}
            placeholder="22:00"
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }}
          />

          <Text style={{ color: colors.mutedText, fontSize: 12 }}>Quiet hours end (HH:MM)</Text>
          <TextInput
            value={notifPrefs.quiet_hours_end_local}
            onChangeText={(v) => setNotifPrefs((p) => ({ ...p, quiet_hours_end_local: v }))}
            placeholder="07:00"
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }}
          />

          <Text style={{ color: colors.mutedText, fontSize: 12 }}>Timezone</Text>
          <TextInput
            value={notifPrefs.timezone}
            onChangeText={(v) => setNotifPrefs((p) => ({ ...p, timezone: v }))}
            placeholder="America/New_York"
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }}
          />

          <Pressable
            onPress={saveNotificationPrefs}
            disabled={notifSaving}
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, opacity: notifSaving ? 0.7 : 1 }}
          >
            <Text style={{ textAlign: "center", fontWeight: "700" }}>{notifSaving ? "Saving..." : "Save notification settings"}</Text>
          </Pressable>
        </View>

        <View style={{ backgroundColor: "white", borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }}>
          <Text style={{ fontWeight: "800", color: colors.text }}>Your vibe card</Text>
          <Text style={{ color: colors.mutedText }}>View your latest vibe card and save a snapshot.</Text>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable
              onPress={loadVibeCard}
              disabled={vibeLoading}
              style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, opacity: vibeLoading ? 0.7 : 1 }}
            >
              <Text style={{ textAlign: "center", fontWeight: "700" }}>{vibeLoading ? "Loading..." : "View vibe card"}</Text>
            </Pressable>
            <Pressable
              onPress={saveVibeCard}
              disabled={vibeSaving}
              style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, opacity: vibeSaving ? 0.7 : 1 }}
            >
              <Text style={{ textAlign: "center", fontWeight: "700" }}>{vibeSaving ? "Saving..." : "Save snapshot"}</Text>
            </Pressable>
          </View>
          {vibeCard ? (
            <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 10, backgroundColor: "#F8FAFC" }}>
              <Text style={{ fontWeight: "800", color: colors.text }}>{String(vibeCard.title || "Your Vibe")}</Text>
              {Array.isArray(vibeCard.adjectives) && vibeCard.adjectives.length ? (
                <Text style={{ color: colors.mutedText, marginTop: 6 }}>Adjectives: {vibeCard.adjectives.join(", ")}</Text>
              ) : null}
              {Array.isArray(vibeCard.strengths) && vibeCard.strengths.length ? (
                <Text style={{ color: colors.mutedText, marginTop: 4 }}>Strengths: {vibeCard.strengths.join(" • ")}</Text>
              ) : null}
              {vibeCard.watch_out ? <Text style={{ color: colors.mutedText, marginTop: 4 }}>Watch-out: {String(vibeCard.watch_out)}</Text> : null}
            </View>
          ) : null}
        </View>

        <View style={{ backgroundColor: "white", borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }}>
          <Text style={{ fontWeight: "800", color: colors.text }}>Feedback to developer</Text>
          <TextInput value={feedback} onChangeText={setFeedback} placeholder="What should we improve?" multiline style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, minHeight: 80 }} />
          <Pressable onPress={async () => { await api.sendDevFeedback(feedback); setFeedback(""); Alert.alert("Thanks", "Feedback sent"); }} style={{ backgroundColor: colors.primary, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", color: "white", fontWeight: "700" }}>Send feedback</Text></Pressable>
        </View>

        <View style={{ backgroundColor: "white", borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }}>
          <Text style={{ fontWeight: "800", color: colors.text }}>Safety</Text>
          <Text style={{ color: colors.mutedText }}>
            Use safety tools any time you feel uncomfortable. Blocking prevents future matches with that person.
            Reporting alerts the CBS Match team about this week’s match and helps us review issues quickly.
          </Text>
          <TextInput
            value={blockIdentifier}
            onChangeText={setBlockIdentifier}
            placeholder="User ID, email, or username to block"
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }}
          />
          <Pressable
            onPress={async () => {
              setBlocking(true);
              try {
                const trimmed = blockIdentifier.trim();
                if (!trimmed) {
                  Alert.alert("Missing info", "Enter a user ID, email, or username.");
                  return;
                }
                const res: any = await api.blockUser(trimmed);
                setBlockIdentifier("");
                await qc.invalidateQueries({ queryKey: ["current-match"] });
                await qc.invalidateQueries({ queryKey: ["match-history"] });
                Alert.alert("Blocked", `Blocked user ${res?.blocked_user_id || ""}. If this was your current match, it is now hidden.`);
              } catch (e) {
                Alert.alert("Could not block", e instanceof Error ? e.message : "Try another identifier");
              } finally {
                setBlocking(false);
              }
            }}
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, opacity: blocking ? 0.7 : 1 }}
          ><Text style={{ textAlign: "center", fontWeight: "700" }}>{blocking ? "Blocking..." : "Block user"}</Text></Pressable>
          <Text style={{ color: colors.mutedText, fontSize: 12 }}>
            When you block someone, they are excluded from your future match pool.
          </Text>
          <TextInput
            value={reportReason}
            onChangeText={setReportReason}
            placeholder="Reason (for example: safety, harassment, no-show)"
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10 }}
          />
          <Pressable
            onPress={async () => {
              const reason = reportReason.trim();
              if (!reason) {
                Alert.alert("Missing info", "Please enter a reason before reporting.");
                return;
              }
              await api.reportCurrentMatch(reason);
              setReportReason("");
              Alert.alert("Reported", "Safety report saved");
            }}
            style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12 }}
          ><Text style={{ textAlign: "center", fontWeight: "700" }}>Report current match</Text></Pressable>
          <Text style={{ color: colors.mutedText, fontSize: 12 }}>
            Reports are private and reviewed by the team. Reporting does not notify your match.
          </Text>
        </View>

        <View style={{ backgroundColor: "white", borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 8 }}>
          <Text style={{ fontWeight: "800", color: colors.text }}>Account</Text>
          <Text style={{ color: colors.mutedText }}>Manage your session and account.</Text>
          <View style={{ gap: 8 }}>
            <Pressable onPress={changeCommunity} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, backgroundColor: "white" }}>
              <Text style={{ textAlign: "center", fontWeight: "700" }}>Change community</Text>
            </Pressable>
            <Pressable onPress={logout} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, backgroundColor: "white" }}>
              <Text style={{ textAlign: "center", fontWeight: "700" }}>Logout</Text>
            </Pressable>
            <Pressable onPress={deleteAccount} style={{ borderWidth: 1, borderColor: "#FECACA", borderRadius: 12, padding: 12, backgroundColor: "#FEF2F2" }}>
              <Text style={{ textAlign: "center", fontWeight: "700", color: "#B91C1C" }}>Delete account</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

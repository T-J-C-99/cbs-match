import React, { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "../api/endpoints";
import { useAppStore } from "../store/appStore";
import { removeSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";
import { colors } from "../theme/colors";

export default function RegisterScreen({ navigation }: any) {
  const setUserId = useAppStore((s) => s.setUserId);
  const setUserEmail = useAppStore((s) => s.setUserEmail);
  const setStoredUsername = useAppStore((s) => s.setUsername);
  const setIsEmailVerified = useAppStore((s) => s.setIsEmailVerified);
  const setAccessToken = useAppStore((s) => s.setAccessToken);
  const setRefreshToken = useAppStore((s) => s.setRefreshToken);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const setHasCompletedSurvey = useAppStore((s) => s.setHasCompletedSurvey);
  const setHasRequiredProfile = useAppStore((s) => s.setHasRequiredProfile);

  const [email, setEmail] = useState("");
  const [username, setUsernameInput] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [usernameStatus, setUsernameStatus] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const checkUsername = async (raw: string) => {
    const value = raw.trim().toLowerCase();
    if (!value) {
      setUsernameStatus(null);
      return;
    }
    if (!/^[a-z0-9_]{3,24}$/.test(value)) {
      setUsernameStatus("Use 3-24 lowercase letters, numbers, or underscores.");
      return;
    }
    try {
      const data = await api.checkUsernameAvailability(value);
      setUsernameStatus(data.available ? "Username is available." : "Username is taken.");
    } catch (e) {
      setUsernameStatus(e instanceof Error ? e.message : "Could not check username");
    }
  };

  const submit = async () => {
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const reg = await api.register(email, password, username.trim().toLowerCase() || undefined);

      if (!("access_token" in reg) || !("refresh_token" in reg)) {
        setMessage(reg.message || "Check your email for a verification code.");
        navigation.navigate("VerifyEmail", { email, code: reg.dev_only?.verification_code || "" });
        return;
      }

      const tokens = reg;
      setAccessToken(tokens.access_token);
      setRefreshToken(tokens.refresh_token);
      await Promise.all([
        setSecureItem(STORAGE_KEYS.accessToken, tokens.access_token),
        setSecureItem(STORAGE_KEYS.refreshToken, tokens.refresh_token),
      ]);

      const me = await api.me();
      const userState = await api.userState();

      const activeSessionId = userState.onboarding.has_completed_survey ? null : userState.onboarding.active_session_id;
      const hasCompletedSurvey = userState.onboarding.has_completed_survey;
      const hasRequiredProfile = userState.profile?.has_required_profile ?? false;

      setUserId(me.id);
      setUserEmail(me.email);
      setStoredUsername(me.username ?? null);
      setIsEmailVerified(me.is_email_verified);
      setSessionId(activeSessionId);
      setHasCompletedSurvey(hasCompletedSurvey);
      setHasRequiredProfile(hasRequiredProfile);

      await Promise.all([
        setSecureItem(STORAGE_KEYS.userId, me.id),
        setSecureItem(STORAGE_KEYS.userEmail, me.email),
        me.username ? setSecureItem(STORAGE_KEYS.username, me.username) : removeSecureItem(STORAGE_KEYS.username),
        setSecureItem(STORAGE_KEYS.isEmailVerified, String(me.is_email_verified)),
        setSecureItem(STORAGE_KEYS.hasOnboarded, "true"),
        setSecureItem(STORAGE_KEYS.hasCompletedSurvey, String(hasCompletedSurvey)),
        setSecureItem(STORAGE_KEYS.hasRequiredProfile, String(hasRequiredProfile)),
        activeSessionId ? setSecureItem(STORAGE_KEYS.sessionId, activeSessionId) : removeSecureItem(STORAGE_KEYS.sessionId),
      ]);

      setMessage("Account created. Let’s build your profile after survey.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Register failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top", "bottom"]}>
      <View style={{ flex: 1, padding: 20, gap: 12, justifyContent: "center" }}>
        <Text style={{ fontSize: 28, fontWeight: "700" }}>Register</Text>
        <TextInput autoCapitalize="none" value={email} onChangeText={setEmail} placeholder="you@gsb.columbia.edu" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, backgroundColor: colors.surface }} />
        <TextInput autoCapitalize="none" value={username} onChangeText={setUsernameInput} onBlur={() => checkUsername(username)} placeholder="username (optional)" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, backgroundColor: colors.surface }} />
        {usernameStatus ? <Text style={{ color: colors.mutedText, fontSize: 12 }}>{usernameStatus}</Text> : null}
        <TextInput secureTextEntry={!showPassword} value={password} onChangeText={setPassword} placeholder="Password (min 10 chars)" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, backgroundColor: colors.surface }} />
        <Pressable onPress={() => setShowPassword((v) => !v)}>
          <Text style={{ textAlign: "right", color: colors.mutedText }}>{showPassword ? "Hide password" : "Show password"}</Text>
        </Pressable>
        {message ? <Text style={{ color: colors.success }}>{message}</Text> : null}
        {error ? <Text style={{ color: colors.danger }}>{error}</Text> : null}
        <Pressable onPress={submit} style={{ backgroundColor: colors.primary, borderRadius: 10, padding: 12, opacity: loading ? 0.7 : 1 }}>
          <Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>{loading ? "Submitting..." : "Create account"}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

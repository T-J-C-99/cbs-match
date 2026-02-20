import React, { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "../api/endpoints";
import { useAppStore } from "../store/appStore";
import { removeSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";
import { colors } from "../theme/colors";

export default function LoginScreen({ navigation }: any) {
  const apiBaseUrl = useAppStore((s) => s.apiBaseUrl);
  const setUserId = useAppStore((s) => s.setUserId);
  const setUserEmail = useAppStore((s) => s.setUserEmail);
  const setUsername = useAppStore((s) => s.setUsername);
  const setIsEmailVerified = useAppStore((s) => s.setIsEmailVerified);
  const setAccessToken = useAppStore((s) => s.setAccessToken);
  const setRefreshToken = useAppStore((s) => s.setRefreshToken);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const setHasCompletedSurvey = useAppStore((s) => s.setHasCompletedSurvey);
  const setHasRequiredProfile = useAppStore((s) => s.setHasRequiredProfile);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const doLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const identifier = email.trim();
      const tokens = await api.login(identifier, password);
      setAccessToken(tokens.access_token);
      setRefreshToken(tokens.refresh_token);
      await Promise.all([
        setSecureItem(STORAGE_KEYS.accessToken, tokens.access_token),
        setSecureItem(STORAGE_KEYS.refreshToken, tokens.refresh_token),
      ]);

      const me = await api.me();
      const userState = await api.userState();

      setUserId(me.id);
      setUserEmail(me.email);
      setUsername(me.username ?? null);
      setIsEmailVerified(me.is_email_verified);

      const activeSessionId = userState.onboarding.has_completed_survey
        ? null
        : userState.onboarding.active_session_id;
      const hasCompletedSurvey = userState.onboarding.has_completed_survey;
      const hasRequiredProfile = userState.profile?.has_required_profile ?? true;
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
        activeSessionId
          ? setSecureItem(STORAGE_KEYS.sessionId, activeSessionId)
          : removeSecureItem(STORAGE_KEYS.sessionId),
      ]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Login failed";
      if (msg.toLowerCase().includes("invalid credentials")) {
        setError(`Invalid credentials. Confirm email and password, and confirm API base URL in Settings is correct (${apiBaseUrl}).`);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top", "bottom"]}>
      <View style={{ flex: 1, padding: 20, gap: 12, justifyContent: "center" }}>
        <Text style={{ fontSize: 28, fontWeight: "700" }}>Login</Text>
        <Text style={{ color: colors.mutedText, fontSize: 12 }}>API: {apiBaseUrl}</Text>
        <TextInput autoCapitalize="none" value={email} onChangeText={setEmail} placeholder="you@gsb.columbia.edu" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, backgroundColor: colors.surface }} />
        <TextInput secureTextEntry={!showPassword} value={password} onChangeText={setPassword} placeholder="Password" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, backgroundColor: colors.surface }} />
        <Pressable onPress={() => setShowPassword((v) => !v)}>
          <Text style={{ textAlign: "right", color: colors.mutedText }}>{showPassword ? "Hide password" : "Show password"}</Text>
        </Pressable>
        {error ? <Text style={{ color: colors.danger }}>{error}</Text> : null}
        <Pressable onPress={doLogin} style={{ backgroundColor: colors.primary, borderRadius: 10, padding: 12, opacity: loading ? 0.7 : 1 }}>
          <Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>{loading ? "Loading..." : "Login"}</Text>
        </Pressable>
        <Pressable onPress={() => navigation.navigate("Register")}>
          <Text style={{ textAlign: "center", color: colors.mutedText }}>Create account</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

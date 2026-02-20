import React from "react";
import { Pressable, Text, View } from "react-native";
import { useMutation } from "@tanstack/react-query";

import ErrorBanner from "../components/ErrorBanner";
import { api } from "../api/endpoints";
import { useAppStore } from "../store/appStore";
import { getSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";

export default function StartSurveyScreen({ navigation }: any) {
  const sessionId = useAppStore((s) => s.sessionId);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const hasCompletedSurvey = useAppStore((s) => s.hasCompletedSurvey);

  React.useEffect(() => {
    if (hasCompletedSurvey) {
      navigation.getParent()?.navigate("Match");
    }
  }, [hasCompletedSurvey, navigation]);

  const mutation = useMutation({
    mutationFn: async () => {
      const stored = await getSecureItem(STORAGE_KEYS.sessionId);
      if (stored) {
        setSessionId(stored);
        return stored;
      }
      const created = await api.createSession();
      setSessionId(created.session_id);
      await setSecureItem(STORAGE_KEYS.sessionId, created.session_id);
      return created.session_id;
    },
    onSuccess: () => {
      navigation.navigate("SurveyRenderer");
    }
  });

  return (
    <View style={{ flex: 1, padding: 20, gap: 12 }}>
      <Text style={{ fontSize: 24, fontWeight: "700" }}>Survey</Text>
      <Text style={{ color: "#475569" }}>{sessionId ? "Resume your saved session" : "Start your first session"}</Text>
      {mutation.error ? <ErrorBanner message={(mutation.error as Error).message} onRetry={() => mutation.mutate()} /> : null}
      <Pressable
        onPress={() => mutation.mutate()}
        style={{ marginTop: 8, backgroundColor: "#111827", borderRadius: 10, padding: 14, opacity: mutation.isPending ? 0.7 : 1 }}
      >
        <Text style={{ textAlign: "center", color: "white", fontWeight: "700" }}>{mutation.isPending ? "Loading..." : sessionId ? "Resume" : "Start survey"}</Text>
      </Pressable>
    </View>
  );
}

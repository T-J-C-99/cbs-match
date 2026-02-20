import React, { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useMutation, useQuery } from "@tanstack/react-query";
import * as Haptics from "expo-haptics";
import { computeCompletion, isItemVisible, nextScreenIndex, resolveOptions } from "@cbs-match/shared";

import { api } from "../api/endpoints";
import LoadingBlock from "../components/LoadingBlock";
import ErrorBanner from "../components/ErrorBanner";
import { useAppStore } from "../store/appStore";
import { removeSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";

export default function SurveyRendererScreen({ navigation }: any) {
  const sessionId = useAppStore((s) => s.sessionId);
  const setSessionId = useAppStore((s) => s.setSessionId);
  const setHasCompletedSurvey = useAppStore((s) => s.setHasCompletedSurvey);
  const hasCompletedSurvey = useAppStore((s) => s.hasCompletedSurvey);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [screenIndex, setScreenIndex] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const surveyQ = useQuery({ queryKey: ["survey"], queryFn: api.getSurvey });
  const sessionQ = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId!),
    enabled: Boolean(sessionId)
  });

  useEffect(() => {
    if (hasCompletedSurvey) {
      navigation.getParent()?.navigate("Match");
      return;
    }
  }, [hasCompletedSurvey, navigation]);

  useEffect(() => {
    if (sessionQ.data?.answers) {
      setAnswers(sessionQ.data.answers as Record<string, any>);
    }
  }, [sessionQ.data]);

  useEffect(() => {
    if (!surveyQ.data) return;
    setScreenIndex(nextScreenIndex(surveyQ.data as any, answers as any));
  }, [surveyQ.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: Array<{ question_code: string; answer_value: unknown }>) => api.saveAnswers(sessionId!, payload)
  });

  const completeMutation = useMutation({
    mutationFn: () => api.completeSession(sessionId!),
    onSuccess: async () => {
      await removeSecureItem(STORAGE_KEYS.sessionId);
      await setSecureItem(STORAGE_KEYS.hasCompletedSurvey, "true");
      setSessionId(null);
      setHasCompletedSurvey(true);
      navigation.getParent()?.navigate("Match");
    }
  });

  const screen = useMemo(() => surveyQ.data?.screens?.[screenIndex], [surveyQ.data, screenIndex]);
  const visibleItems = useMemo(() => (screen?.items || []).filter((item: any) => isItemVisible(item, answers as any)), [screen, answers]);

  const valid = visibleItems.every((item: any) => {
    const q = item.question;
    if (q.allow_skip || !q.is_required) return true;
    const v = answers[q.code];
    return v !== undefined && v !== null && `${v}`.length > 0;
  });

  const onAnswer = (code: string, value: unknown) => {
    Haptics.selectionAsync();
    setAnswers((prev) => ({ ...prev, [code]: value }));

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      saveMutation.mutate([{ question_code: code, answer_value: value }]);
    }, 300);
  };

  if (surveyQ.isLoading || sessionQ.isLoading) {
    return (
      <View style={{ flex: 1, padding: 20 }}>
        <LoadingBlock lines={8} />
      </View>
    );
  }

  if (surveyQ.error || sessionQ.error) {
    return (
      <View style={{ flex: 1, padding: 20 }}>
        <ErrorBanner
          message={(surveyQ.error as Error)?.message || (sessionQ.error as Error)?.message || "Could not load survey"}
          onRetry={() => {
            surveyQ.refetch();
            sessionQ.refetch();
          }}
        />
      </View>
    );
  }

  if (!screen || !surveyQ.data) return null;

  const completion = computeCompletion(surveyQ.data as any, answers as any);
  const isLast = screenIndex === surveyQ.data.screens.length - 1;

  return (
    <View style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }}>
        <Text style={{ fontSize: 12, color: "#64748b" }}>Progress {completion}%</Text>
        <Text style={{ fontSize: 24, fontWeight: "700" }}>{screen.title}</Text>
        {!!screen.subtitle && <Text style={{ color: "#64748b" }}>{screen.subtitle}</Text>}

        {visibleItems.map((item: any) => {
          const q = item.question;
          const value = answers[q.code];
          const options = resolveOptions(item, surveyQ.data.option_sets);
          return (
            <View key={q.code} style={{ gap: 8, padding: 12, borderRadius: 12, backgroundColor: "white" }}>
              <Text style={{ fontWeight: "600" }}>{q.text}</Text>
              {q.response_type === "likert_1_5" ? (
                <View style={{ flexDirection: "row", gap: 8 }}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Pressable
                      key={n}
                      onPress={() => onAnswer(q.code, n)}
                      style={{
                        flex: 1,
                        alignItems: "center",
                        paddingVertical: 10,
                        borderRadius: 8,
                        backgroundColor: value === n ? "#0f172a" : "#e2e8f0"
                      }}
                    >
                      <Text style={{ color: value === n ? "white" : "#0f172a", fontWeight: "700" }}>{n}</Text>
                    </Pressable>
                  ))}
                </View>
              ) : (
                <View style={{ gap: 8 }}>
                  {options.map((opt: any) => {
                    const selected = value === opt.value;
                    return (
                      <Pressable
                        key={`${q.code}-${opt.value}`}
                        onPress={() => onAnswer(q.code, opt.value)}
                        style={{ borderRadius: 10, borderWidth: 1, borderColor: selected ? "#0f172a" : "#cbd5e1", backgroundColor: selected ? "#e2e8f0" : "white", padding: 12 }}
                      >
                        <Text>{opt.label}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>

      <View style={{ flexDirection: "row", gap: 12, padding: 16 }}>
        <Pressable
          onPress={() => setScreenIndex((v) => Math.max(0, v - 1))}
          disabled={screenIndex === 0}
          style={{ flex: 1, borderRadius: 10, borderWidth: 1, borderColor: "#cbd5e1", padding: 12, opacity: screenIndex === 0 ? 0.5 : 1 }}
        >
          <Text style={{ textAlign: "center", fontWeight: "700" }}>Back</Text>
        </Pressable>

        <Pressable
          onPress={() => {
            if (isLast) {
              completeMutation.mutate();
              return;
            }
            setScreenIndex((v) => Math.min(v + 1, surveyQ.data.screens.length - 1));
          }}
          disabled={!valid || completeMutation.isPending}
          style={{ flex: 1, borderRadius: 10, backgroundColor: "#111827", padding: 12, opacity: !valid ? 0.5 : 1 }}
        >
          <Text style={{ textAlign: "center", color: "white", fontWeight: "700" }}>{isLast ? "Complete" : "Next"}</Text>
        </Pressable>
      </View>
    </View>
  );
}

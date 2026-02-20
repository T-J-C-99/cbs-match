import React from "react";
import { Pressable, Text, View } from "react-native";

import { useAppStore } from "../store/appStore";
import { setSecureItem, STORAGE_KEYS } from "../utils/storage";

export default function WelcomeScreen({ navigation }: any) {
  const setHasOnboarded = useAppStore((s) => s.setHasOnboarded);

  const onStart = async () => {
    setHasOnboarded(true);
    await setSecureItem(STORAGE_KEYS.hasOnboarded, "true");
  };

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 14 }}>
      <Text style={{ fontSize: 30, fontWeight: "700" }}>CBS Match</Text>
      <Text style={{ color: "#475569" }}>Find your fit through a short questionnaire and weekly matching.</Text>
      <Pressable onPress={onStart} style={{ backgroundColor: "#0f172a", padding: 14, borderRadius: 10 }}>
        <Text style={{ color: "white", fontWeight: "700", textAlign: "center" }}>Start</Text>
      </Pressable>
      <Pressable onPress={() => navigation.navigate("DevSettings")}>
        <Text style={{ color: "#334155", textAlign: "center" }}>Developer settings</Text>
      </Pressable>
    </View>
  );
}

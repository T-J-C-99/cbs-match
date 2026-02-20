import React, { useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, Text, View, Image } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { colors } from "../theme/colors";
import { SafeAreaView } from "react-native-safe-area-context";

function initials(name?: string | null) {
  const parts = String(name || "Match").split(" ").filter(Boolean);
  return (parts[0]?.[0] || "M") + (parts[1]?.[0] || "");
}

function Bullet({ text }: { text: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-start" }}>
      <Text style={{ width: 16, lineHeight: 20 }}>•</Text>
      <Text style={{ flex: 1, lineHeight: 20 }}>{text}</Text>
    </View>
  );
}

export default function PastScreen() {
  const [selected, setSelected] = useState<any | null>(null);
  const q = useQuery({ queryKey: ["match-history"], queryFn: () => api.getMatchHistory(12) });
  const items = useMemo(() => q.data?.history || [], [q.data]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top"]}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
        <Text style={{ fontSize: 28, fontWeight: "800", color: colors.text }}>Past matches</Text>
        {!items.length && !q.isLoading ? (
          <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 16, backgroundColor: colors.surface, padding: 14, gap: 4 }}>
            <Text style={{ fontWeight: "700", color: colors.text }}>No past cycles yet</Text>
            <Text style={{ color: colors.mutedText }}>The Dean of Dating is still building your history. Once matches cycle through, they’ll appear here.</Text>
          </View>
        ) : null}
        {items.map((item: any, i: number) => {
          const profile = item.matched_profile || {};
          const photo = Array.isArray(profile.photo_urls) ? profile.photo_urls[0] : undefined;
          return (
            <Pressable key={`${item.week_start_date}-${i}`} onPress={() => setSelected(item)} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 16, backgroundColor: colors.surface, padding: 10 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                {photo ? (
                  <Image source={{ uri: photo }} style={{ width: 56, aspectRatio: 4 / 5, borderRadius: 10 }} resizeMode="cover" />
                ) : (
                  <View style={{ width: 56, aspectRatio: 4 / 5, borderRadius: 10, alignItems: "center", justifyContent: "center", backgroundColor: "#dbeafe" }}><Text style={{ fontWeight: "700" }}>{initials(profile.display_name)}</Text></View>
                )}
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "700", color: colors.text }}>{profile.display_name || "No match"}</Text>
                  <Text style={{ color: colors.mutedText, fontSize: 12 }}>Week of {item.week_start_date}</Text>
                </View>
                <Text style={{ fontSize: 12, color: colors.mutedText }}>{item.status}</Text>
              </View>
            </Pressable>
          );
        })}
      </ScrollView>

      <Modal visible={!!selected} transparent animationType="slide" onRequestClose={() => setSelected(null)}>
        <View style={{ flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(15,39,66,0.35)" }}>
          <View style={{ backgroundColor: "white", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, maxHeight: "80%", gap: 8 }}>
            <Text style={{ fontWeight: "800", fontSize: 22, color: colors.text }}>{selected?.matched_profile?.display_name || "Past match"}</Text>
            <Text style={{ color: colors.mutedText }}>Week of {selected?.week_start_date}</Text>
            <Text style={{ fontWeight: "700", marginTop: 8, color: colors.text }}>The Dean’s summary</Text>
            <Text style={{ color: colors.text, lineHeight: 20 }}>{selected?.explanation_v2?.overall || "Compatibility summary unavailable."}</Text>

            <Text style={{ fontWeight: "700", marginTop: 8, color: colors.text }}>Contact info</Text>
            {selected?.matched_profile?.email ? <Bullet text={`Email: ${selected.matched_profile.email}`} /> : null}
            {selected?.matched_profile?.phone_number ? <Bullet text={`Phone: ${selected.matched_profile.phone_number}`} /> : null}
            {selected?.matched_profile?.instagram_handle ? <Bullet text={`Instagram: @${selected.matched_profile.instagram_handle}`} /> : null}
            {!selected?.matched_profile?.email && !selected?.matched_profile?.phone_number && !selected?.matched_profile?.instagram_handle ? (
              <Bullet text="No direct contact info was shared for this cycle." />
            ) : null}

            <Pressable onPress={() => setSelected(null)} style={{ marginTop: 16, backgroundColor: colors.primary, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", color: "white", fontWeight: "700" }}>Close</Text></Pressable>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

import React from "react";
import { Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { getTenants } from "@cbs-match/shared";

import { colors } from "../theme/colors";
import { useAppStore } from "../store/appStore";
import { setSecureItem, STORAGE_KEYS } from "../utils/storage";

export default function AuthLandingScreen({ navigation }: any) {
  const tenants = getTenants();
  const setTenantSlug = useAppStore((s) => s.setTenantSlug);

  const chooseTenant = async (slug: string) => {
    setTenantSlug(slug);
    await setSecureItem(STORAGE_KEYS.tenantSlug, slug);
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top", "bottom"]}>
      <View style={{ flex: 1, paddingHorizontal: 24, paddingVertical: 20, justifyContent: "center", gap: 16 }}>
        <Text style={{ color: colors.mutedText, textTransform: "uppercase", letterSpacing: 1 }}>CBS Match M7</Text>
        <Text style={{ fontSize: 34, fontWeight: "800", color: colors.text }}>Choose your community</Text>
        <Text style={{ color: colors.mutedText }}>
          Select your school, then create an account or log in.
        </Text>

        <View style={{ gap: 8 }}>
          {tenants.map((t) => (
            <Pressable
              key={t.slug}
              onPress={() => chooseTenant(t.slug)}
              style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 10, backgroundColor: "white" }}
            >
              <Text style={{ fontWeight: "700", color: colors.text }}>{t.name}</Text>
              <Text style={{ fontSize: 12, color: colors.mutedText }}>{t.tagline}</Text>
            </Pressable>
          ))}
        </View>

        <Pressable onPress={() => navigation.navigate("Register")} style={{ backgroundColor: colors.primary, borderRadius: 12, padding: 14 }}>
          <Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>Create account</Text>
        </Pressable>
        <Pressable onPress={() => navigation.navigate("Login")} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 14, backgroundColor: "white" }}>
          <Text style={{ textAlign: "center", fontWeight: "700", color: colors.text }}>Log in</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

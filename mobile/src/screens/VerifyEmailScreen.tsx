import React, { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { api } from "../api/endpoints";

export default function VerifyEmailScreen({ navigation, route }: any) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState<string | null>("Enter your email and 6-digit code.");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const emailFromNav = route?.params?.email;
    const codeFromNav = route?.params?.code;
    if (emailFromNav && typeof emailFromNav === "string") setEmail(emailFromNav);
    if (codeFromNav && typeof codeFromNav === "string") setCode(codeFromNav);
  }, [route?.params?.email, route?.params?.code]);

  const verify = async () => {
    setError(null);
    try {
      await api.verifyEmail(email.trim(), code.trim());
      setMessage("Email verified. You can login now.");
      navigation.navigate("Login");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed");
    }
  };

  return (
    <View style={{ flex: 1, padding: 20, gap: 12, justifyContent: "center" }}>
      <Text style={{ fontSize: 26, fontWeight: "700" }}>Verify email</Text>
      <Text style={{ color: "#475569" }}>Use the 6-digit code from email (or dev logs).</Text>
      <TextInput autoCapitalize="none" value={email} onChangeText={setEmail} placeholder="you@gsb.columbia.edu" style={{ borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 10, padding: 10 }} />
      <TextInput autoCapitalize="none" value={code} onChangeText={setCode} placeholder="6-digit code" style={{ borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 10, padding: 10 }} />
      {message ? <Text style={{ color: "#166534" }}>{message}</Text> : null}
      {error ? <Text style={{ color: "#b91c1c" }}>{error}</Text> : null}
      <Pressable onPress={verify} style={{ backgroundColor: "#0f172a", borderRadius: 10, padding: 12 }}>
        <Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>Verify code</Text>
      </Pressable>
    </View>
  );
}

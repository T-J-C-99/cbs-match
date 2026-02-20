import React from "react";
import { Pressable, Text, View } from "react-native";

export default function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View style={{ backgroundColor: "#fee2e2", borderRadius: 10, padding: 12, marginVertical: 8 }}>
      <Text style={{ color: "#991b1b", marginBottom: onRetry ? 8 : 0 }}>{message}</Text>
      {onRetry ? (
        <Pressable onPress={onRetry} style={{ alignSelf: "flex-start", paddingVertical: 6, paddingHorizontal: 10, backgroundColor: "#991b1b", borderRadius: 6 }}>
          <Text style={{ color: "white", fontWeight: "600" }}>Retry</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

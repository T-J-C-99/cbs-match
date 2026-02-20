import React from "react";
import { View } from "react-native";

export default function LoadingBlock({ lines = 4 }: { lines?: number }) {
  return (
    <View style={{ gap: 10 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <View key={i} style={{ height: 14, borderRadius: 8, backgroundColor: "#e2e8f0" }} />
      ))}
    </View>
  );
}

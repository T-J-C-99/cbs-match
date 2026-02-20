import { Platform } from "react-native";

export function defaultApiBaseUrl() {
  if (process.env.EXPO_PUBLIC_API_BASE_URL) return process.env.EXPO_PUBLIC_API_BASE_URL;
  if (Platform.OS === "android") return "http://10.0.2.2:8000";
  return "http://localhost:8000";
}

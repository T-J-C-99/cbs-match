import "react-native-gesture-handler";
import React, { useMemo } from "react";
import { ActivityIndicator, View } from "react-native";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useBootstrap } from "./src/hooks/useBootstrap";
import StartSurveyScreen from "./src/screens/StartSurveyScreen";
import SurveyRendererScreen from "./src/screens/SurveyRendererScreen";
import MatchScreen from "./src/screens/MatchScreen";
import PastScreen from "./src/screens/PastScreen";
import ProfileScreen from "./src/screens/ProfileScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import LoginScreen from "./src/screens/LoginScreen";
import RegisterScreen from "./src/screens/RegisterScreen";
import VerifyEmailScreen from "./src/screens/VerifyEmailScreen";
import AuthLandingScreen from "./src/screens/AuthLandingScreen";
import { useAppStore } from "./src/store/appStore";
import { colors, getColorsForTenant } from "./src/theme/colors";

const queryClient = new QueryClient();
const RootStack = createNativeStackNavigator();
const AuthStack = createNativeStackNavigator();
const SurveyStack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

function AuthNavigator() {
  return (
    <AuthStack.Navigator initialRouteName="AuthLanding" screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="AuthLanding" component={AuthLandingScreen} options={{ title: "CBS Match" }} />
      <AuthStack.Screen name="Login" component={LoginScreen} options={{ title: "Login" }} />
      <AuthStack.Screen name="Register" component={RegisterScreen} options={{ title: "Register" }} />
      <AuthStack.Screen name="VerifyEmail" component={VerifyEmailScreen} options={{ title: "Verify email" }} />
    </AuthStack.Navigator>
  );
}

function SurveyNavigator() {
  return (
    <SurveyStack.Navigator>
      <SurveyStack.Screen name="StartSurvey" component={StartSurveyScreen} options={{ title: "Survey" }} />
      <SurveyStack.Screen name="SurveyRenderer" component={SurveyRendererScreen} options={{ title: "Questionnaire" }} />
    </SurveyStack.Navigator>
  );
}

function icon(name: string, focused: boolean) {
  const map: Record<string, keyof typeof Ionicons.glyphMap> = {
    Match: focused ? "heart" : "heart-outline",
    Past: focused ? "time" : "time-outline",
    Profile: focused ? "person" : "person-outline",
    Settings: focused ? "settings" : "settings-outline",
    Survey: focused ? "document-text" : "document-text-outline",
  };
  return map[name] || "ellipse-outline";
}

function AppTabs({ hasCompletedSurvey, hasRequiredProfile }: { hasCompletedSurvey: boolean; hasRequiredProfile: boolean }) {
  const insets = useSafeAreaInsets();

  return (
    <Tabs.Navigator
      initialRouteName={hasCompletedSurvey ? "Match" : "Survey"}
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          height: 58 + insets.bottom,
          paddingTop: 6,
          paddingBottom: Math.max(insets.bottom, 8),
          borderTopColor: colors.border,
          backgroundColor: "white",
        },
        tabBarItemStyle: { alignItems: "center", justifyContent: "center" },
        tabBarLabelStyle: { fontSize: 12, fontWeight: "600", marginTop: 0 },
        tabBarIconStyle: { marginTop: 0 },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.mutedText,
        tabBarIcon: ({ color, focused, size }) => <Ionicons name={icon(route.name, focused)} color={color} size={size} />,
      })}
    >
      {!hasCompletedSurvey ? <Tabs.Screen name="Survey" component={SurveyNavigator} /> : null}
      <Tabs.Screen name="Match" component={MatchScreen} />
      <Tabs.Screen name="Past" component={PastScreen} />
      <Tabs.Screen name="Profile" component={ProfileScreen} />
      <Tabs.Screen name="Settings" component={SettingsScreen} />
    </Tabs.Navigator>
  );
}

export default function App() {
  const { ready, hasAuth } = useBootstrap();
  const hasCompletedSurvey = useAppStore((s) => s.hasCompletedSurvey);
  const hasRequiredProfile = useAppStore((s) => s.hasRequiredProfile);
  const tenantSlug = useAppStore((s) => s.tenantSlug);
  const tenantColors = getColorsForTenant(tenantSlug);

  const navTheme = useMemo(
    () => ({ ...DefaultTheme, colors: { ...DefaultTheme.colors, background: tenantColors.background, primary: tenantColors.primary, text: tenantColors.text, card: tenantColors.surface, border: tenantColors.border } }),
    [tenantColors.background, tenantColors.border, tenantColors.primary, tenantColors.surface, tenantColors.text]
  );

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <NavigationContainer theme={navTheme}>
          <RootStack.Navigator screenOptions={{ headerShown: false }}>
            {!hasAuth ? (
              <RootStack.Screen name="Auth" component={AuthNavigator} />
            ) : (
              <RootStack.Screen name="AppTabs">
                {() => <AppTabs hasCompletedSurvey={hasCompletedSurvey} hasRequiredProfile={hasRequiredProfile} />}
              </RootStack.Screen>
            )}
          </RootStack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}

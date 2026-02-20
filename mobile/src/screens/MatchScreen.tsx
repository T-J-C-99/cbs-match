import React, { useEffect, useMemo, useState } from "react";
import { Alert, Image, Linking, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { colors } from "../theme/colors";
import { SafeAreaView } from "react-native-safe-area-context";
import { getSecureItem, setSecureItem, STORAGE_KEYS } from "../utils/storage";

// Clean vector icons matching web
function EmailIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      {/* Envelope body */}
      <View style={{ width: size, height: size * 0.7, borderWidth: 1.2, borderColor: color, borderRadius: 2 }}>
        {/* V shape inside */}
        <View style={{ position: "absolute", top: -1, left: 0, right: 0, height: size * 0.5, alignItems: "center", justifyContent: "center" }}>
          <View style={{ width: size * 0.85, height: 1.2, backgroundColor: color, transform: [{ rotate: "20deg" }] }} />
        </View>
        <View style={{ position: "absolute", top: -1, left: 0, right: 0, height: size * 0.5, alignItems: "center", justifyContent: "center" }}>
          <View style={{ width: size * 0.85, height: 1.2, backgroundColor: color, transform: [{ rotate: "-20deg" }] }} />
        </View>
      </View>
    </View>
  );
}

function PhoneIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      {/* Phone handset - curved receiver */}
      <View style={{ width: size * 0.35, height: size * 0.9, position: "relative" }}>
        {/* Top curve */}
        <View style={{ width: size * 0.6, height: size * 0.3, borderWidth: 1.2, borderColor: color, borderRadius: size * 0.15, position: "absolute", top: 0, left: -size * 0.12 }} />
        {/* Bottom curve */}
        <View style={{ width: size * 0.6, height: size * 0.3, borderWidth: 1.2, borderColor: color, borderRadius: size * 0.15, position: "absolute", bottom: 0, left: -size * 0.12 }} />
      </View>
    </View>
  );
}

function InstagramIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      {/* Rounded square */}
      <View style={{ width: size, height: size, borderWidth: 1.2, borderColor: color, borderRadius: size * 0.2, alignItems: "center", justifyContent: "center" }}>
        {/* Circle */}
        <View style={{ width: size * 0.45, height: size * 0.45, borderWidth: 1.2, borderColor: color, borderRadius: size * 0.225 }} />
        {/* Dot */}
        <View style={{ position: "absolute", top: size * 0.15, right: size * 0.15, width: size * 0.1, height: size * 0.1, backgroundColor: color, borderRadius: size * 0.05 }} />
      </View>
    </View>
  );
}

const FALLBACK_PROS = [
  "This pairing has a natural conversation baseline.",
  "You likely share enough overlap to enjoy a first meetup.",
];
const FALLBACK_CONS = [
  "You may have different defaults around planning and pace.",
  "Set expectations early for smoother follow-through.",
];

export default function MatchScreen() {
  const qc = useQueryClient();
  const [photoIdx, setPhotoIdx] = useState(0);
  const [showContact, setShowContact] = useState(false);
  const [showRevealCover, setShowRevealCover] = useState(false);
  const [excited, setExcited] = useState(4);
  const [messaged, setMessaged] = useState<"yes" | "no" | null>(null);
  const [feedbackSubmittedFor, setFeedbackSubmittedFor] = useState<string | null>(null);

  const q = useQuery({ queryKey: ["current-match"], queryFn: api.getCurrentMatch });
  const feedback = useMutation({
    mutationFn: () => {
      const answers: Record<string, unknown> = { coffee_intent: excited };
      if (q.data?.feedback?.due_met_question) {
        answers.met = messaged === "yes";
      }
      return api.submitFeedback(answers);
    },
    onSuccess: () => {
      setFeedbackSubmittedFor(matchKey);
      qc.invalidateQueries({ queryKey: ["current-match"] });
    },
    onError: (e) => {
      Alert.alert("Could not submit", e instanceof Error ? e.message : "Try again");
    }
  });

  const profile = q.data?.match?.matched_profile;
  const hasMatch = !!profile?.id && q.data?.match?.status !== "no_match";
  const photos: string[] = (profile?.photo_urls || []).slice(0, 3);
  const explanation = q.data?.explanation_v2;
  const matchKey = `${q.data?.match?.week_start_date || "none"}:${profile?.id || "none"}`;
  const feedbackSubmitted = feedbackSubmittedFor === matchKey || Boolean(q.data?.feedback?.already_submitted);
  const pros = useMemo(() => Array.from(new Set((explanation?.pros || FALLBACK_PROS))).slice(0, 2), [explanation]);
  const cons = useMemo(() => Array.from(new Set((explanation?.cons || FALLBACK_CONS))).slice(0, 2), [explanation]);
  const deanOverallFallbacks = [
    "The Dean of Dating ran the numbers and this pairing has momentum worth testing in person.",
    "The Dean of Dating sees complementary vibes here—good odds for an engaging first coffee.",
    "The Dean of Dating’s read: this match has enough alignment to make a real week-one spark possible.",
  ];
  const deanIdx = Math.abs(matchKey.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0)) % deanOverallFallbacks.length;
  const overallCopy = explanation?.overall || deanOverallFallbacks[deanIdx];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const hasVisibleMatch = !!profile?.id && q.data?.match?.status !== "no_match";
      if (!hasVisibleMatch) {
        if (!cancelled) setShowRevealCover(false);
        return;
      }
      const seen = await getSecureItem(STORAGE_KEYS.lastSeenMatchKey);
      if (!cancelled) setShowRevealCover(seen !== matchKey);
    })();
    return () => {
      cancelled = true;
    };
  }, [matchKey, profile?.id, q.data?.match?.status]);

  const revealMatch = async () => {
    await setSecureItem(STORAGE_KEYS.lastSeenMatchKey, matchKey);
    setShowRevealCover(false);
  };

  const email = profile?.email || "";
  const phone = (profile as any)?.phone_number || "";
  const instagram = (profile as any)?.instagram_handle || "";

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["top"]}>
      <ScrollView style={{ flex: 1, backgroundColor: colors.background }} contentContainerStyle={{ padding: 16, gap: 14 }}>
        <View>
          <Text style={{ fontSize: 30, fontWeight: "800", color: colors.text }}>{hasMatch ? "This week’s match" : "No match this week"}</Text>
          <Text style={{ color: colors.mutedText, marginTop: 2 }}>
            {q.data?.match?.week_start_date ? `Week of ${q.data.match.week_start_date}` : "The Dean is finalizing this week’s match math."}
          </Text>
        </View>

        {!hasMatch ? (
          <View style={{ borderRadius: 18, overflow: "hidden", backgroundColor: "white", borderWidth: 1, borderColor: colors.border, padding: 16, gap: 6 }}>
            <Text style={{ fontSize: 20, fontWeight: "800", color: colors.text }}>No match yet</Text>
            <Text style={{ color: colors.mutedText }}>We did not find a pairing for you this cycle. Keep your profile complete and check back next week.</Text>
          </View>
        ) : <View style={{ borderRadius: 18, overflow: "hidden", backgroundColor: "white", borderWidth: 1, borderColor: colors.border }}>
          {photos.length ? (
            <>
              <Image source={{ uri: photos[photoIdx % photos.length] }} style={{ width: "100%", aspectRatio: 4 / 5 }} resizeMode="cover" />
              {photos.length > 1 ? (
                <View style={{ position: "absolute", top: 0, bottom: 0, left: 10, right: 10, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                  <Pressable onPress={() => setPhotoIdx((n) => (n - 1 + photos.length) % photos.length)} style={{ backgroundColor: "rgba(0,0,0,0.35)", borderRadius: 20, paddingHorizontal: 10, paddingVertical: 6 }}><Text style={{ color: "white" }}>‹</Text></Pressable>
                  <Pressable onPress={() => setPhotoIdx((n) => (n + 1) % photos.length)} style={{ backgroundColor: "rgba(0,0,0,0.35)", borderRadius: 20, paddingHorizontal: 10, paddingVertical: 6 }}><Text style={{ color: "white" }}>›</Text></Pressable>
                </View>
              ) : null}
            </>
          ) : (
            <View style={{ width: "100%", aspectRatio: 4 / 5, alignItems: "center", justifyContent: "center", backgroundColor: "#dbeafe" }}>
              <Text style={{ fontSize: 48, fontWeight: "800", color: colors.primary }}>{String(profile?.display_name || "M").slice(0, 1)}</Text>
            </View>
          )}

          <View style={{ padding: 14, gap: 8 }}>
            <Text style={{ fontSize: 28, fontWeight: "800", color: colors.text }}>{profile?.display_name || "Your match"}</Text>
            <Text style={{ color: colors.mutedText }}>CBS {profile?.cbs_year || "—"}{profile?.hometown ? ` • ${profile.hometown}` : ""}</Text>
            
            {/* Sleek contact action buttons */}
            {(email || phone || instagram) && (
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                {email && (
                  <Pressable 
                    onPress={() => Linking.openURL(`mailto:${email}`)} 
                    style={{ backgroundColor: colors.primary, borderRadius: 24, paddingHorizontal: 16, paddingVertical: 10, flexDirection: "row", alignItems: "center", gap: 6 }}
                  >
                    <EmailIcon size={16} color="white" />
                    <Text style={{ color: "white", fontWeight: "600" }}>Email</Text>
                  </Pressable>
                )}
                {phone && (
                  <Pressable 
                    onPress={async () => {
                      // Remove any non-numeric characters except + for proper SMS URL
                      const cleanPhone = phone.replace(/[^\d+]/g, "");
                      console.log("Opening SMS with phone:", cleanPhone, "(original:", phone, ")");
                      try {
                        const supported = await Linking.canOpenURL(`sms:${cleanPhone}`);
                        if (supported) {
                          await Linking.openURL(`sms:${cleanPhone}`);
                        } else {
                          Alert.alert("Phone Number", cleanPhone);
                        }
                      } catch (e) {
                        console.error("SMS error:", e);
                        Alert.alert("Phone Number", cleanPhone);
                      }
                    }} 
                    style={{ borderWidth: 2, borderColor: colors.primary, borderRadius: 24, paddingHorizontal: 16, paddingVertical: 10, flexDirection: "row", alignItems: "center", gap: 6 }}
                  >
                    <PhoneIcon size={16} color={colors.primary} />
                    <Text style={{ color: colors.primary, fontWeight: "600" }}>Text</Text>
                  </Pressable>
                )}
                {instagram && (
                  <Pressable 
                    onPress={() => {
                      // Remove @ if present at the start
                      const handle = instagram.startsWith("@") ? instagram.slice(1) : instagram;
                      console.log("Opening Instagram for handle:", handle);
                      Linking.openURL(`https://instagram.com/${handle}`);
                    }} 
                    style={{ backgroundColor: "#E1306C", borderRadius: 24, paddingHorizontal: 16, paddingVertical: 10, flexDirection: "row", alignItems: "center", gap: 6 }}
                  >
                    <InstagramIcon size={16} color="white" />
                    <Text style={{ color: "white", fontWeight: "600" }}>Follow</Text>
                  </Pressable>
                )}
              </View>
            )}
          </View>
        </View>}

        {hasMatch ? (
          <View style={{ backgroundColor: "white", borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 8 }}>
            <Text style={{ fontWeight: "800", color: colors.text, fontSize: 18 }}>The Dean of Dating’s take</Text>
            <Text style={{ color: colors.text }}>{overallCopy}</Text>
            <Text style={{ fontWeight: "800", color: colors.text, marginTop: 6 }}>Strengths</Text>
            {pros.map((p) => <View key={p} style={{ flexDirection: "row", alignItems: "flex-start" }}><Text style={{ width: 16 }}>•</Text><Text style={{ flex: 1 }}>{p}</Text></View>)}
            <Text style={{ fontWeight: "800", color: colors.text, marginTop: 6 }}>Considerations</Text>
            {cons.map((c) => <View key={c} style={{ flexDirection: "row", alignItems: "flex-start" }}><Text style={{ width: 16 }}>•</Text><Text style={{ flex: 1 }}>{c}</Text></View>)}
          </View>
        ) : (
          <View style={{ backgroundColor: "white", borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 8 }}>
            <Text style={{ fontWeight: "800", color: colors.text, fontSize: 18 }}>What to do next</Text>
            <Text style={{ color: colors.text }}>No action needed right now. You’ll be reconsidered in the next weekly cycle.</Text>
          </View>
        )}

        {!hasMatch ? null : !feedbackSubmitted ? <View style={{ backgroundColor: "white", borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 8 }}>
          <Text style={{ fontWeight: "800", color: colors.text, fontSize: 18 }}>Quick feedback</Text>
          <Text style={{ color: colors.mutedText }}>Internal only. This helps improve matching. Not shared with your match.</Text>
          <Text style={{ fontWeight: "600", color: colors.text }}>How excited are you to meet?</Text>
          <View style={{ flexDirection: "row", gap: 8 }}>{[1,2,3,4,5].map((n) => <Pressable key={n} onPress={() => setExcited(n)} style={{ flex: 1, borderWidth: 1, borderColor: excited === n ? colors.primary : colors.border, borderRadius: 10, padding: 8, backgroundColor: excited === n ? colors.primary : "white" }}><Text style={{ textAlign: "center", color: excited === n ? "white" : colors.text, fontWeight: "700" }}>{n}</Text></Pressable>)}</View>
          {q.data?.feedback?.due_met_question ? (
            <>
              <Text style={{ fontWeight: "600", color: colors.text }}>Did you message them? (optional)</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>{(["yes","no"] as const).map((v) => <Pressable key={v} onPress={() => setMessaged(v)} style={{ flex: 1, borderWidth: 1, borderColor: messaged === v ? colors.primary : colors.border, borderRadius: 10, padding: 10, backgroundColor: messaged === v ? colors.primary : "white" }}><Text style={{ textAlign: "center", color: messaged === v ? "white" : colors.text, fontWeight: "700" }}>{v.toUpperCase()}</Text></Pressable>)}</View>
            </>
          ) : null}
          <Pressable onPress={() => feedback.mutate()} style={{ backgroundColor: colors.primary, borderRadius: 12, padding: 12, marginTop: 4, opacity: feedback.isPending ? 0.7 : 1 }}><Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>{feedback.isPending ? "Saving..." : "Submit"}</Text></Pressable>
        </View> : (
          <View style={{ backgroundColor: "#ECFDF3", borderRadius: 16, padding: 14, borderWidth: 1, borderColor: "#A6F4C5", gap: 6 }}>
            <Text style={{ fontWeight: "800", color: "#166534", fontSize: 17 }}>Feedback received</Text>
            <Text style={{ color: "#166534" }}>The Dean of Dating logged your notes for this match. Thanks for helping improve weekly pairings.</Text>
          </View>
        )}

        <Modal visible={showContact} transparent animationType="slide" onRequestClose={() => setShowContact(false)}>
          <View style={{ flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(15,39,66,0.35)" }}>
            <View style={{ backgroundColor: "white", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, gap: 10 }}>
              <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text }}>{profile?.display_name || "Contact"}</Text>
              <Text style={{ color: colors.text }}>{email || phone || instagram ? "Choose a contact method below." : "No direct contact on file. Find them in the CBS directory / Slack / Instagram."}</Text>
              {email ? <Pressable onPress={() => Alert.alert("Email", email)} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", fontWeight: "700" }}>Email: {email}</Text></Pressable> : null}
              {phone ? <Pressable onPress={() => Alert.alert("Phone", phone)} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", fontWeight: "700" }}>Phone: {phone}</Text></Pressable> : null}
              {instagram ? <Pressable onPress={() => Alert.alert("Instagram", `@${instagram}`)} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", fontWeight: "700" }}>Instagram: @{instagram}</Text></Pressable> : null}
              <Pressable onPress={() => setShowContact(false)} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12 }}><Text style={{ textAlign: "center", fontWeight: "700" }}>Close</Text></Pressable>
            </View>
          </View>
        </Modal>
      </ScrollView>

      <Modal visible={showRevealCover} transparent animationType="fade" onRequestClose={revealMatch}>
        <View style={{ flex: 1, backgroundColor: "rgba(15,39,66,0.72)", justifyContent: "center", padding: 20 }}>
          <View style={{ backgroundColor: "white", borderRadius: 16, padding: 18, gap: 10 }}>
            <Text style={{ color: colors.mutedText, textTransform: "uppercase", letterSpacing: 1 }}>From the Dean of Dating</Text>
            <Text style={{ fontSize: 26, fontWeight: "800", color: colors.text }}>Your new match is in.</Text>
            <Text style={{ color: colors.text, lineHeight: 20 }}>
              I reviewed your profile and this week’s cohort. I think this pairing has strong potential if you actually meet in person.
            </Text>
            <Pressable onPress={revealMatch} style={{ marginTop: 6, backgroundColor: colors.primary, borderRadius: 12, padding: 12 }}>
              <Text style={{ color: "white", textAlign: "center", fontWeight: "700" }}>Reveal my match</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

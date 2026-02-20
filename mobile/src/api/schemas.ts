import { z } from "zod";

export const optionSchema = z.object({ value: z.union([z.string(), z.number()]), label: z.string() });

export const surveySchema = z.object({
  survey: z.object({ slug: z.string(), version: z.number() }),
  option_sets: z.record(z.array(optionSchema)),
  screens: z.array(
    z.object({
      key: z.string(),
      ordinal: z.number(),
      title: z.string(),
      subtitle: z.string().optional(),
      items: z.array(
        z.object({
          question: z.object({
            code: z.string(),
            text: z.string(),
            response_type: z.union([z.literal("likert_1_5"), z.literal("single_select"), z.literal("forced_choice_pair")]),
            is_required: z.boolean(),
            allow_skip: z.boolean(),
            ui_hint: z.string().optional(),
            reverse_coded: z.boolean().optional(),
            region_tag: z.union([z.literal("GLOBAL"), z.literal("CBS_NYC")]).optional(),
            usage: z.union([z.literal("SCORING"), z.literal("COPY_ONLY")]).optional(),
          }),
          options: z.union([z.string(), z.array(optionSchema)]).optional(),
          rules: z.array(
            z.object({
              type: z.literal("show_if"),
              trigger_question_code: z.string(),
              operator: z.union([z.literal("eq"), z.literal("neq"), z.literal("in"), z.literal("not_in")]),
              trigger_value: z.union([z.string(), z.number(), z.array(z.union([z.string(), z.number()]))])
            })
          )
        })
      )
    })
  )
});

export const authTokenSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string(),
  expires_in: z.number()
});

export const authRegisterResponseSchema = z.union([
  authTokenSchema,
  z.object({
    message: z.string(),
    dev_only: z.object({ verification_code: z.string() }).optional(),
  }),
]);

export const authMeSchema = z.object({
  id: z.string(),
  email: z.string(),
  username: z.string().nullable().optional(),
  is_email_verified: z.boolean()
});

export const userStateSchema = z.object({
  user: z.object({
    id: z.string().optional(),
    email: z.string().optional(),
    username: z.string().nullable().optional(),
    is_email_verified: z.boolean().optional(),
  }).optional(),
  onboarding: z.object({
    has_any_session: z.boolean(),
    has_completed_survey: z.boolean(),
    survey_outdated: z.boolean().optional(),
    active_survey_slug: z.string().optional(),
    active_survey_version: z.number().optional(),
    active_session_id: z.string().nullable(),
    latest_completed_session_at: z.string().nullable().optional(),
  }),
  profile: z.object({
    has_required_profile: z.boolean(),
    missing_fields: z.array(z.string())
  }).optional(),
  latest_traits: z.any().optional(),
  current_traits: z.any().optional(),
  latest_traits_computed_at: z.string().nullable().optional(),
  current_traits_computed_at: z.string().nullable().optional(),
});

export const userProfileSchema = z.object({
  profile: z.object({
    id: z.string(),
    email: z.string(),
    display_name: z.string().nullable(),
    cbs_year: z.string().nullable(),
    hometown: z.string().nullable(),
    phone_number: z.string().nullable().optional(),
    instagram_handle: z.string().nullable().optional(),
    gender_identity: z.string().nullable().optional(),
    seeking_genders: z.array(z.string()).optional(),
    photo_urls: z.array(z.string())
  })
});

export const vibeCardSchema = z.object({
  survey_slug: z.string().optional(),
  survey_version: z.number().optional(),
  created_at: z.string().optional(),
  saved: z.boolean().optional(),
  vibe_card: z.record(z.any()).optional(),
  vibe: z.object({
    title: z.string().optional(),
    three_bullets: z.array(z.string()).optional(),
    one_watchout: z.string().optional(),
    best_date_energy: z.object({ key: z.string().optional(), label: z.string().optional() }).optional(),
    opener_style: z.object({ key: z.string().optional(), template: z.string().optional() }).optional(),
    compatibility_motto: z.string().optional(),
  }).optional(),
});

export const notificationPreferencesSchema = z.object({
  preferences: z.object({
    email_enabled: z.boolean(),
    push_enabled: z.boolean(),
    quiet_hours_start_local: z.string().nullable().optional(),
    quiet_hours_end_local: z.string().nullable().optional(),
    timezone: z.string(),
    updated_at: z.string().nullable().optional(),
  }),
});

export const sessionResponseSchema = z.object({ session_id: z.string(), user_id: z.string() });
export const sessionDetailSchema = z.object({
  session: z.object({ id: z.string(), status: z.string(), user_id: z.string() }),
  answers: z.record(z.any())
});

export const matchSchema = z.object({
  match: z.any().nullable(),
  message: z.string(),
  explanation: z.object({
    bullets: z.array(z.string()),
    summary: z.array(z.string()).optional(),
    icebreakers: z.array(z.string()),
    highlights: z.array(z.string()).optional(),
    potential_challenges: z.array(z.string()).optional(),
    uniqueness: z.array(z.string()).optional(),
  }).optional(),
  explanation_v2: z.object({
    overall: z.string(),
    pros: z.array(z.string()),
    cons: z.array(z.string()),
    version: z.string()
  }).optional(),
  feedback: z.object({ eligible: z.boolean(), already_submitted: z.boolean(), due_met_question: z.boolean() }).optional()
});

export const matchHistorySchema = z.object({
  history: z.array(
    z.object({
      week_start_date: z.string(),
      status: z.string(),
      matched_profile: z.object({
        id: z.string().nullable().optional(),
        email: z.string().nullable().optional(),
        phone_number: z.string().nullable().optional(),
        instagram_handle: z.string().nullable().optional(),
        display_name: z.string().nullable().optional(),
        cbs_year: z.string().nullable().optional(),
        hometown: z.string().nullable().optional(),
        photo_urls: z.array(z.string()).optional()
      }).optional(),
      explanation_v2: z.object({
        overall: z.string(),
        pros: z.array(z.string()),
        cons: z.array(z.string()),
        version: z.string()
      }).optional()
    })
  )
});

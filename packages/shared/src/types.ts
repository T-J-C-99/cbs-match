export type Primitive = string | number | boolean | null;
export type AnswerValue = Primitive | Primitive[];

// Keep this union aligned with API and web semantics.
// Unknown operators must be treated as non-matching (fail closed).
export type ShowIfOperator = "eq" | "neq" | "in" | "not_in";

export type ShowIfRule = {
  type: "show_if";
  trigger_question_code: string;
  operator: ShowIfOperator;
  trigger_value: Primitive | Primitive[];
};

export type Question = {
  code: string;
  text: string;
  response_type: "likert_1_5" | "single_select" | "forced_choice_pair";
  is_required: boolean;
  allow_skip: boolean;
  ui_hint?: string;
  reverse_coded?: boolean;
  region_tag?: "GLOBAL" | "CBS_NYC";
  usage?: "SCORING" | "COPY_ONLY";
};

export type Option = {
  value: Primitive;
  label: string;
};

export type Item = {
  question: Question;
  options?: string | Option[];
  rules: ShowIfRule[];
};

export type Screen = {
  key: string;
  ordinal: number;
  title: string;
  subtitle?: string;
  ui_layout?: string;
  items: Item[];
};

export type SurveySchema = {
  survey: {
    slug: string;
    version: number;
    name: string;
    status: string;
    estimated_minutes?: number;
    created_at?: string;
  };
  option_sets: Record<string, Option[]>;
  screens: Screen[];
};

export type AnswersMap = Record<string, AnswerValue | undefined>;

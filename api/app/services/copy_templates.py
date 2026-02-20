"""
Dean of Dating Dynamic Copy Machine

Generates personalized match explanations using mad-libs style templates
populated with actual compatibility data from the matching algorithm.
"""

from typing import Any
import random


# =============================================================================
# DOMAIN LABELS - Human-readable names for each compatibility dimension
# =============================================================================

DOMAIN_LABELS = {
    "big5": {
        "openness": "curiosity and openness to new experiences",
        "conscientiousness": "follow-through and planning style",
        "extraversion": "social energy and engagement",
        "agreeableness": "warmth and cooperation",
        "neuroticism": "emotional sensitivity",
    },
    "life_architecture": {
        "marriage": "long-term partnership vision",
        "kids": "family planning",
        "nyc": "NYC commitment",
        "career_intensity": "career ambition",
        "faith": "values and faith",
        "social_lifestyle": "social lifestyle",
    },
    "conflict_style": {
        "repair_willingness": "repair after disagreement",
        "escalation": "conflict escalation style",
        "cooldown_need": "need for cooldown space",
        "grudge_tendency": "letting go of tension",
    },
}

# Short versions for compact copy
DOMAIN_SHORT = {
    "big5": {
        "openness": "Curiosity",
        "conscientiousness": "Follow-through",
        "extraversion": "Social Energy",
        "agreeableness": "Warmth",
        "neuroticism": "Emotional Style",
    },
    "life_architecture": {
        "marriage": "Life Architecture",
        "kids": "Family Planning",
        "nyc": "NYC Commitment",
        "career_intensity": "Career Ambition",
        "faith": "Values",
        "social_lifestyle": "Social Lifestyle",
    },
    "conflict_style": {
        "repair_willingness": "Conflict Repair",
        "escalation": "Conflict Style",
        "cooldown_need": "Personal Space",
        "grudge_tendency": "Moving Forward",
    },
}


# =============================================================================
# TEMPLATE LIBRARY - Mad-libs style copy with {placeholders}
# =============================================================================

OVERALL_TEMPLATES = {
    # High compatibility templates (score >= 0.72)
    "high": [
        "The Dean of Dating has crunched the numbers, and this is a standout pairing. Your {top_alignment} alignment is notable—you're working from a similar playbook.",
        "This match caught the Dean's eye. You two show real potential, especially in your shared approach to {top_alignment}.",
        "The Dean of Dating sees strong fundamentals here. Your alignment on {top_alignment} gives this match a solid foundation to build on.",
        "After running the compatibility math, the Dean of Dating is confident this pairing has legs. Your {top_alignment} sync is particularly promising.",
        "The Dean of Dating's analysis reveals a high-potential connection. Your shared perspective on {top_alignment} suggests natural chemistry.",
    ],
    # Medium compatibility templates (0.58 <= score < 0.72)
    "medium": [
        "The Dean of Dating has identified a worthwhile connection here. Your {top_alignment} alignment provides a good starting point for conversation.",
        "This match passes the Dean's compatibility thresholds. You show meaningful alignment on {top_alignment}, which can anchor your first conversation.",
        "The Dean of Dating sees potential in this pairing. While not a perfect match on paper, your {top_alignment} sync suggests room to grow.",
        "After careful analysis, the Dean of Dating thinks this is worth exploring. Your shared approach to {top_alignment} could create real connection.",
        "The Dean's compatibility math shows a solid baseline. Your alignment around {top_alignment} is worth a conversation.",
    ],
    # Lower compatibility templates (score < 0.58)
    "low": [
        "The Dean of Dating sees a challenging but interesting pairing. Your differences around {gap_area} will require intentional communication.",
        "This match requires some homework, according to the Dean. Your {gap_area} differences mean clear conversations early will matter.",
        "The Dean of Dating detected some style gaps—particularly around {gap_area}. Naming these early can prevent friction.",
        "Not the easiest match on paper, but the Dean sees a path. Your different approaches to {gap_area} could actually complement each other.",
        "The Dean's analysis shows you'll need to navigate some differences, especially in {gap_area}. Worth discussing early.",
    ],
}

PROS_TEMPLATES = {
    # Big 5 personality alignment
    "big5_aligned": [
        "Your {trait} styles are well-matched ({score}% similar), which should make conversations flow naturally.",
        "You both approach {trait} in compatible ways—this creates a natural understanding.",
        "Your {score}% alignment on {trait} means you likely read situations similarly.",
        "The Dean sees real {trait} compatibility here ({score}%), which often predicts easy rapport.",
    ],
    "big5_complementary": [
        "Your different approaches to {trait} could create interesting balance—you fill each other's gaps.",
        "Where one leans one way on {trait}, the other balances it out—this can work well.",
        "Your {trait} differences might create helpful perspective-taking between you.",
    ],
    
    # Conflict style alignment
    "conflict_aligned": [
        "You handle conflict similarly, which reduces friction when tensions arise.",
        "Your conflict-repair styles are aligned—neither of you lets things fester.",
        "The Dean likes that you both approach disagreements with a similar repair mindset.",
    ],
    
    # Life architecture alignment
    "life_aligned": [
        "You share similar views on {domain}, which removes a common source of tension.",
        "Your {domain} preferences align well—this creates implicit understanding.",
        "The Dean sees {domain} alignment here, which often makes day-to-day decisions easier.",
    ],
    
    # High scores overall
    "high_score": [
        "Your compatibility score ({score}%) is strong, suggesting natural rapport potential.",
        "The Dean's algorithms rate this match {score}% compatible—that's above average.",
        "This pairing scores {score}% on the Dean's compatibility index, indicating real promise.",
    ],
    
    # General positive
    "general": [
        "This pairing has a natural conversation baseline.",
        "You likely share enough overlap to enjoy a first meetup.",
        "Your overall profiles suggest you'll find common ground quickly.",
        "The Dean sees enough alignment to recommend a real-world test.",
    ],
}

CONS_TEMPLATES = {
    # Big 5 gaps
    "big5_gap": [
        "Your biggest style gap appears in {trait}—naming expectations early can prevent friction.",
        "You may have different defaults around {trait}, so check in on this early.",
        "The Dean noticed a {trait} gap between you—worth a conversation to align expectations.",
    ],
    
    # Life architecture gaps
    "life_gap": [
        "You may have different perspectives on {domain}. A quick conversation can clarify.",
        "Your {domain} preferences differ slightly—worth understanding each other's priorities.",
        "The Dean flagged {domain} as an area where you'll want to align early.",
    ],
    
    # Conflict style gaps
    "conflict_gap": [
        "You may have different approaches to handling tension—explicit check-ins will help.",
        "Your conflict styles differ slightly, so clarity on repair expectations matters.",
    ],
    
    # Modifier penalties
    "modifier_penalty": [
        "Some life-preference tradeoffs may need explicit conversation—clarity early will help.",
        "A few preference differences to navigate, but nothing the Dean hasn't seen work before.",
    ],
    
    # General watch-outs
    "general": [
        "You may have different defaults around planning and pace.",
        "Set expectations early for smoother follow-through.",
        "First-impression chemistry may depend on finding the right setting.",
        "A short coffee can quickly test whether your styles mesh in person.",
    ],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _num(v: Any) -> float | None:
    """Safely convert to float."""
    try:
        return float(v) if isinstance(v, (int, float)) else None
    except (TypeError, ValueError):
        return None


def _traits_big5(traits: dict[str, Any] | None) -> dict[str, Any]:
    t = traits or {}
    # Support both legacy schema (big5) and current match-core-v3 schema (big_five + stability).
    big5 = t.get("big5") or t.get("big_five") or {}
    if not isinstance(big5, dict):
        big5 = {}
    out = dict(big5)
    if "neuroticism" not in out:
        stability = _num(((t.get("emotional_regulation") or {}).get("stability")))
        if stability is not None:
            out["neuroticism"] = 1.0 - stability
    return out


def _conflict_repair_willingness(traits: dict[str, Any] | None) -> float | None:
    t = traits or {}
    legacy = (t.get("conflict_repair") or {}) if isinstance(t.get("conflict_repair"), dict) else {}
    if "repair_willingness" in legacy:
        return _num(legacy.get("repair_willingness"))
    current = (t.get("conflict") or {}) if isinstance(t.get("conflict"), dict) else {}
    return _num(current.get("repair_belief"))


def _conflict_cooldown_need(traits: dict[str, Any] | None) -> float | None:
    t = traits or {}
    legacy = (t.get("conflict_repair") or {}) if isinstance(t.get("conflict_repair"), dict) else {}
    if "cooldown_need" in legacy:
        return _num(legacy.get("cooldown_need"))
    current = (t.get("conflict") or {}) if isinstance(t.get("conflict"), dict) else {}
    # Withdrawal is the closest v3 analogue to needing cooldown space.
    return _num(current.get("withdrawal"))


def _pct(v: float | None) -> str:
    """Format as percentage string."""
    if v is None:
        return "--"
    return f"{round(v * 100)}"


def _bucket(v: float | None) -> str:
    """Categorize score into bucket."""
    if v is None:
        return "unknown"
    if v >= 0.8:
        return "very high"
    if v >= 0.65:
        return "high"
    if v >= 0.5:
        return "moderate"
    return "developing"


def _get_top_big5_alignment(user_traits: dict, matched_traits: dict) -> tuple[str, float]:
    """Find the Big5 trait with highest similarity (smallest gap)."""
    ub = _traits_big5(user_traits)
    mb = _traits_big5(matched_traits)
    
    candidates = []
    for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
        u = _num(ub.get(k))
        m = _num(mb.get(k))
        if u is not None and m is not None:
            # Similarity is inverse of gap
            similarity = 1.0 - abs(u - m)
            candidates.append((k, similarity))
    
    if not candidates:
        return ("social energy", 0.5)
    
    # Return most similar trait
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0]


def _get_top_big5_gap(user_traits: dict, matched_traits: dict) -> tuple[str, float]:
    """Find the Big5 trait with largest gap."""
    ub = _traits_big5(user_traits)
    mb = _traits_big5(matched_traits)
    
    candidates = []
    for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
        u = _num(ub.get(k))
        m = _num(mb.get(k))
        if u is not None and m is not None:
            gap = abs(u - m)
            candidates.append((k, gap))
    
    if not candidates:
        return ("follow-through", 0.2)
    
    # Return trait with largest gap
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0]


def _get_life_architecture_alignment(score_breakdown: dict) -> tuple[str, float] | None:
    """Find life architecture domain with best alignment (lowest penalty)."""
    penalties = (score_breakdown or {}).get("modifier_penalties") or {}
    if not penalties:
        return None
    
    # Lower penalty = better alignment
    sorted_domains = sorted(penalties.items(), key=lambda x: x[1], reverse=True)
    if sorted_domains:
        domain, penalty = sorted_domains[0]
        # Convert penalty back to alignment (penalty of 1.0 = perfect, lower = more misaligned)
        return (domain, penalty)
    return None


def _get_life_architecture_gap(score_breakdown: dict) -> tuple[str, float] | None:
    """Find life architecture domain with biggest gap (highest penalty)."""
    penalties = (score_breakdown or {}).get("modifier_penalties") or {}
    if not penalties:
        return None
    
    # Higher penalty = more misalignment
    sorted_domains = sorted(penalties.items(), key=lambda x: x[1])
    if sorted_domains and sorted_domains[0][1] < 0.95:  # Only flag if meaningful gap
        domain, penalty = sorted_domains[0]
        gap = 1.0 - penalty
        return (domain, gap)
    return None


def _select_template(templates: list[str]) -> str:
    """Randomly select a template."""
    return random.choice(templates)


# =============================================================================
# MAIN COPY GENERATION FUNCTIONS
# =============================================================================

def generate_overall_copy(
    score_breakdown: dict[str, Any] | None,
    user_traits: dict[str, Any] | None,
    matched_traits: dict[str, Any] | None,
) -> str:
    """Generate the main Dean of Dating overall assessment."""
    
    score = _num((score_breakdown or {}).get("base_score"))
    
    # Determine score tier
    if score is None:
        tier = "medium"
    elif score >= 0.72:
        tier = "high"
    elif score >= 0.58:
        tier = "medium"
    else:
        tier = "low"
    
    # Get alignment info for placeholder
    top_trait, top_similarity = _get_top_big5_alignment(user_traits, matched_traits)
    trait_label = DOMAIN_LABELS["big5"].get(top_trait, top_trait)
    
    # Get gap info for lower scores
    gap_trait, gap_size = _get_top_big5_gap(user_traits, matched_traits)
    gap_label = DOMAIN_LABELS["big5"].get(gap_trait, gap_trait)
    
    # Select template and fill placeholders
    template = _select_template(OVERALL_TEMPLATES[tier])
    
    if tier == "low":
        return template.format(gap_area=gap_label)
    else:
        return template.format(top_alignment=trait_label)


def generate_pros(
    score_breakdown: dict[str, Any] | None,
    user_traits: dict[str, Any] | None,
    matched_traits: dict[str, Any] | None,
    count: int = 2,
) -> list[str]:
    """Generate pros list based on actual match data."""
    
    pros = []
    score_breakdown = score_breakdown or {}
    user_traits = user_traits or {}
    matched_traits = matched_traits or {}
    
    # 1. Top Big5 alignment
    top_trait, top_similarity = _get_top_big5_alignment(user_traits, matched_traits)
    trait_short = DOMAIN_SHORT["big5"].get(top_trait, top_trait)
    
    if top_similarity >= 0.75:
        template = _select_template(PROS_TEMPLATES["big5_aligned"])
        pros.append(template.format(
            trait=trait_short.lower(),
            score=_pct(top_similarity),
        ))
    elif top_similarity >= 0.5:
        pros.append(f"Your {trait_short.lower()} styles are reasonably aligned ({_pct(top_similarity)}% similar).")
    
    # 2. Overall score if high
    score = _num(score_breakdown.get("base_score"))
    if score is not None and score >= 0.65:
        template = _select_template(PROS_TEMPLATES["high_score"])
        pros.append(template.format(score=_pct(score)))
    
    # 3. Conflict style alignment
    big5_sim = _num(score_breakdown.get("big5_similarity"))
    conflict_sim = _num(score_breakdown.get("conflict_similarity"))
    
    if conflict_sim is not None and conflict_sim >= 0.7:
        pros.append(_select_template(PROS_TEMPLATES["conflict_aligned"]))
    
    # 4. Life architecture alignment
    la_alignment = _get_life_architecture_alignment(score_breakdown)
    if la_alignment and la_alignment[1] >= 0.95:
        domain = la_alignment[0]
        domain_label = DOMAIN_SHORT["life_architecture"].get(domain, domain)
        template = _select_template(PROS_TEMPLATES["life_aligned"])
        pros.append(template.format(domain=domain_label.lower()))
    
    # 5. Fill with general positives if needed
    while len(pros) < count:
        general = _select_template(PROS_TEMPLATES["general"])
        if general not in pros:
            pros.append(general)
    
    return pros[:count]


def generate_cons(
    score_breakdown: dict[str, Any] | None,
    user_traits: dict[str, Any] | None,
    matched_traits: dict[str, Any] | None,
    count: int = 2,
) -> list[str]:
    """Generate cons/watch-outs list based on actual match data."""
    
    cons = []
    score_breakdown = score_breakdown or {}
    user_traits = user_traits or {}
    matched_traits = matched_traits or {}
    
    # 1. Big5 gap
    gap_trait, gap_size = _get_top_big5_gap(user_traits, matched_traits)
    trait_short = DOMAIN_SHORT["big5"].get(gap_trait, gap_trait)
    
    if gap_size >= 0.25:
        template = _select_template(CONS_TEMPLATES["big5_gap"])
        cons.append(template.format(trait=trait_short.lower()))
    
    # 2. Life architecture gap
    la_gap = _get_life_architecture_gap(score_breakdown)
    if la_gap and la_gap[1] >= 0.1:
        domain = la_gap[0]
        domain_label = DOMAIN_SHORT["life_architecture"].get(domain, domain)
        template = _select_template(CONS_TEMPLATES["life_gap"])
        cons.append(template.format(domain=domain_label.lower()))
    
    # 3. Modifier penalties
    modifier = _num(score_breakdown.get("modifier_multiplier"))
    if modifier is not None and modifier < 0.9:
        cons.append(_select_template(CONS_TEMPLATES["modifier_penalty"]))
    
    # 4. Conflict style gap
    conflict_sim = _num(score_breakdown.get("conflict_similarity"))
    if conflict_sim is not None and conflict_sim < 0.5:
        cons.append(_select_template(CONS_TEMPLATES["conflict_gap"]))
    
    # 5. Fill with general watch-outs if needed
    while len(cons) < count:
        general = _select_template(CONS_TEMPLATES["general"])
        if general not in cons:
            cons.append(general)
    
    return cons[:count]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

# =============================================================================
# PROFILE INSIGHTS - Personalized Dean insights for the Profile tab
# =============================================================================

PROFILE_INSIGHT_TEMPLATES = {
    # Big5 personality insights
    "high_openness": [
        "You score high on openness—this often correlates with appreciating intellectual depth and novel experiences in a partner.",
        "Your curiosity threshold is high. You may connect best with someone who brings new perspectives to the table.",
        "High openness suggests you value growth and exploration in relationships.",
        "You're the type who'd try a new restaurant on date one. Adventure is your love language.",
        "Intellectual chemistry probably matters more to you than small talk. The Dean approves.",
    ],
    "high_conscientiousness": [
        "Your follow-through scores are strong—reliability is likely a core value you bring to relationships.",
        "High conscientiousness often means you appreciate structure and planning. A partner who respects that will thrive with you.",
        "You likely bring consistency and intentionality to your connections.",
        "You're the one who actually remembers anniversaries. That's rare and valuable.",
        "Plans with you probably don't get cancelled last minute. Your future partner will notice.",
    ],
    "high_extraversion": [
        "Your social energy is high—you may thrive with someone who can match or complement your engagement level.",
        "Extraversion suggests you recharge through connection. Partner activities may matter more to you than solo downtime.",
        "You light up a room. A partner who appreciates that energy will thrive alongside you.",
        "First dates with you probably aren't awkward. That's half the battle won.",
        "Your social battery runs on connection—perfect for someone who wants a partner-in-crime, not just a partner.",
    ],
    "high_agreeableness": [
        "High agreeableness suggests you bring warmth and cooperation to relationships—a strong foundation for long-term compatibility.",
        "You likely prioritize harmony and may naturally de-escalate tension.",
        "You're probably the one who remembers to ask 'how was your day?'—and actually listens.",
        "Kindness is your default setting. In the dating market, that's undervalued currency.",
    ],
    "low_neuroticism": [
        "Lower emotional reactivity suggests steady calm under pressure—a valuable trait in relationship turbulence.",
        "You may handle stress with resilience, creating stability for your partner.",
        "When things get rocky, you're the anchor. That steadiness is relationship gold.",
        "You're unlikely to spiral over a delayed text. The Dean respects that chill.",
    ],
    "high_neuroticism": [
        "Higher sensitivity means you likely feel deeply. A partner who validates emotions will be important for you.",
        "You may be highly attuned to relationship dynamics—both a strength and something to be mindful of.",
        "You feel things intensely. That makes for passionate connections with the right person.",
        "Your emotional radar is finely tuned. A partner who appreciates depth over surface will match well.",
    ],
    
    # Conflict style insights
    "high_repair": [
        "Your conflict-repair willingness is high—you likely don't let tension linger, which is a relationship superpower.",
        "Quick repair suggests you prioritize reconnection over being right.",
        "You're not one to let a fight stretch into next week. That maturity shows.",
        "The Dean bets you're good at saying 'I'm sorry' when it matters. That's rarer than you think.",
    ],
    "high_cooldown": [
        "You may need space to process after tension. A partner who respects that will help you reconnect faster.",
        "Built-in cooldown needs suggest you process internally before re-engaging. Naming this early helps.",
    ],
    
    # Life architecture insights
    "marriage_aligned": [
        "Your long-term partnership vision is clear. This creates natural alignment with similarly-focused matches.",
    ],
    "career_focused": [
        "Career intensity matters to you. A partner who shares or respects that drive will feel like a better fit.",
    ],
    
    # General insights
    "profile_complete": [
        "Your profile is complete—this improves match quality and shows intentionality.",
        "A complete profile signals you're taking this seriously, which attracts like-minded matches.",
    ],
    "photos_help": [
        "Photos increase your visibility and first-message response rates significantly.",
        "Profiles with photos see substantially more engagement from matches.",
        "Your photos are doing heavy lifting. Good call on that investment.",
    ],
    
    # Fun & flirty insights
    "fun_flirty": [
        "The Dean has a hunch you're more fun than your survey answers let on.",
        "Someone's going to get lucky matching with you. The Dean means 'in love,' obviously.",
        "Your profile suggests depth, charm, and just enough mystery. Nice balance.",
        "The Dean's algorithms detect hidden boyfriend/girlfriend material. Just saying.",
        "You're the type who makes first dates feel less like interviews. That's a skill.",
        "There's something about your profile that screams 'good kisser.' The Dean doesn't make this stuff up.",
        "Your answers suggest you'd be fun at a dinner party AND alone on a couch. Rare combo.",
        "The Dean notices you didn't play it safe on every question. That confidence will translate.",
        "Someone's about to match with you and think, 'how did I get this lucky?'",
        "Your profile has 'catch' energy. The Dean stands by this assessment.",
        "You probably have excellent taste in music. Call it a Dean's intuition.",
        "The Dean suspects you're more romantic than you let on. Time will tell.",
        "Your mix of traits suggests you're low-drama but high-investment. That's premium.",
        "There's a confident undercurrent to your profile. Matches will pick up on that.",
        "The Dean sees main character energy. Find someone who matches that.",
    ],
    
    # Trait combination insights
    "open_and_agreeable": [
        "High openness + high warmth = you're probably that rare person who's interesting AND kind.",
        "Curious and caring? That combination makes for memorable connections.",
    ],
    "conscientious_and_calm": [
        "Reliable and emotionally steady? You're built for the long haul.",
        "The Dean sees 'marriage material' written all over this combo.",
    ],
    "social_and_warm": [
        "Social energy plus genuine warmth—you probably make everyone feel included.",
        "You're likely the one who keeps friend groups together. That translates well to relationships.",
    ],
}


def generate_profile_insights(
    user_traits: dict[str, Any] | None,
    profile_data: dict[str, Any] | None,
    count: int = 4,
) -> list[str]:
    """
    Generate personalized Dean of Dating insights for the Profile tab.
    Based on actual user traits and profile data.
    """
    insights = []
    user_traits = user_traits or {}
    profile_data = profile_data or {}
    
    big5 = _traits_big5(user_traits)
    repair_willingness = _conflict_repair_willingness(user_traits)
    cooldown_need = _conflict_cooldown_need(user_traits)
    
    # Big5-based insights
    if big5.get("openness", 0) >= 0.7:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_openness"]))
    
    if big5.get("conscientiousness", 0) >= 0.7:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_conscientiousness"]))
    
    if big5.get("extraversion", 0) >= 0.7:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_extraversion"]))
    elif big5.get("extraversion", 0) <= 0.3:
        insights.append("Your social energy is more reserved—you may connect best with someone who values quality time over quantity.")
    
    if big5.get("agreeableness", 0) >= 0.7:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_agreeableness"]))
    
    neuroticism = big5.get("neuroticism", 0.5)
    if neuroticism <= 0.3:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["low_neuroticism"]))
    elif neuroticism >= 0.7:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_neuroticism"]))
    
    # Conflict style insights
    if (repair_willingness if repair_willingness is not None else 0) >= 0.7:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_repair"]))
    
    if (cooldown_need if cooldown_need is not None else 0.5) >= 0.6:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["high_cooldown"]))
    
    # Profile-based insights
    photos = profile_data.get("photo_urls") or []
    if len([p for p in photos if p]) >= 1:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["photos_help"]))
    
    # Add a trait summary if we don't have enough
    if len(insights) < count:
        # Calculate overall personality profile
        trait_summary = []
        if big5.get("openness", 0) >= 0.6:
            trait_summary.append("curious")
        if big5.get("conscientiousness", 0) >= 0.6:
            trait_summary.append("reliable")
        if big5.get("extraversion", 0) >= 0.6:
            trait_summary.append("socially energized")
        if big5.get("agreeableness", 0) >= 0.6:
            trait_summary.append("warm")
        
        if trait_summary:
            insights.append(f"The Dean sees your key traits as: {', '.join(trait_summary[:3])}. These shape your match recommendations.")
    
    # Add profile completion insight
    display_name = profile_data.get("display_name")
    if display_name:
        insights.append(f"Your profile is active under '{display_name}'. Keeping it current helps the Dean find better matches.")
    
    # Add trait combination insights
    openness = big5.get("openness", 0.5)
    conscientiousness = big5.get("conscientiousness", 0.5)
    extraversion = big5.get("extraversion", 0.5)
    agreeableness = big5.get("agreeableness", 0.5)
    neuroticism = big5.get("neuroticism", 0.5)
    
    # Open + Agreeable = interesting + kind
    if openness >= 0.65 and agreeableness >= 0.65:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["open_and_agreeable"]))
    
    # Conscientious + Low neuroticism = reliable + steady
    if conscientiousness >= 0.65 and neuroticism <= 0.4:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["conscientious_and_calm"]))
    
    # Extraverted + Agreeable = social + warm
    if extraversion >= 0.65 and agreeableness >= 0.65:
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["social_and_warm"]))
    
    # Add a fun/flirty insight randomly (30% chance)
    if random.random() < 0.3 and PROFILE_INSIGHT_TEMPLATES.get("fun_flirty"):
        insights.append(random.choice(PROFILE_INSIGHT_TEMPLATES["fun_flirty"]))
    
    # Shuffle and return requested count
    random.shuffle(insights)
    return insights[:count]


def build_personalized_explanation(
    score_breakdown: dict[str, Any] | None,
    user_traits: dict[str, Any] | None,
    matched_traits: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Build a fully personalized match explanation using the Dean of Dating's
    dynamic copy machine.
    
    Returns:
        dict with 'overall', 'pros', 'cons', and 'version' keys
    """
    
    overall = generate_overall_copy(score_breakdown, user_traits, matched_traits)
    pros = generate_pros(score_breakdown, user_traits, matched_traits)
    cons = generate_cons(score_breakdown, user_traits, matched_traits)
    
    return {
        "overall": overall,
        "strengths": pros,
        "considerations": cons,
        # Backward compatibility
        "pros": pros,
        "cons": cons,
        "version": "2026-02-17-v3",
    }

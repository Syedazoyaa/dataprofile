"""Dataset quality report for Raven global generator."""
import sys
sys.path.insert(0, ".")
from collections import Counter
from app.generator import generate_profiles
from app.schemas import PROFILE_COLUMNS
from app.geography import COUNTRIES, supported_continents
from app.rules import assess_profile

def main():
    n = 1000
    seed = 7777
    pros = generate_profiles(n, seed, country_mode="global")
    print(f"Total profiles: {len(pros)}")
    countries = Counter(p["country"] for p in pros)
    print(f"Countries represented: {len(countries)} / {len(COUNTRIES)}")
    print(f"Countries missing (sample): {[c for c in COUNTRIES if c not in countries][:5]}")
    continents = Counter(COUNTRIES[p["country"]]["continent"] for p in pros)
    print(f"Continents: {dict(continents)}")
    subregions = Counter(COUNTRIES[p["country"]]["subregion"] for p in pros)
    print(f"Subregions: {len(subregions)} - {dict(list(subregions.items())[:5])}")
    cities = Counter(p["city"] for p in pros)
    print(f"Cities represented: {len(cities)} (sample {list(cities)[:5]})")
    langs = Counter(p["primary_language"] for p in pros)
    print(f"Languages: {len(langs)} - {dict(list(langs.items())[:5])}")
    currs = Counter(p["currency"] for p in pros)
    print(f"Currencies: {len(currs)} - {dict(list(currs.items())[:5])}")
    print(f"Personality distribution: {Counter(p['personality_name'] for p in pros)}")
    # Moderate percentages
    fields = ["decision_speed","comparison_behavior","analytical_orientation","research_before_purchase","premium_preference"]
    for f in fields:
        c = Counter(p[f] for p in pros)
        mod = c.get("Moderate",0)/len(pros)*100
        print(f"  {f}: Moderate {mod:.1f}% {dict(c)}")
    # Duplicates
    seen=set()
    dups=0
    for p in pros:
        key=tuple(p[k] for k in PROFILE_COLUMNS[:10])
        if key in seen:
            dups+=1
        seen.add(key)
    print(f"Duplicate (first 10 cols) : {dups}/{n} ({dups/n*100:.2f}%)")
    # Near-duplicate via behavioral vector
    vecs=[tuple(p.get(k) for k in ["personality_name","openness","conscientiousness","extraversion","decision_speed","analytical_orientation"]) for p in pros]
    near=0
    for i in range(len(vecs)):
        for j in range(i+1, len(vecs)):
            if sum(1 for a,b in zip(vecs[i], vecs[j]) if a!=b) <2:
                near+=1
                break
    print(f"Near-duplicate (dist<2): {near}/{n} ({near/n*100:.2f}%)")
    fails=sum(1 for p in pros if not assess_profile(p)["valid"])
    print(f"Validation failures: {fails}/{n}")
    # Behavioral correlations
    # Example: research vs decision
    print("Sample profiles (different archetypes & continents):")
    for p in pros[::200][:5]:
        print(f"  {p['personality_name']} {p['country']} ({COUNTRIES[p['country']]['continent']}) age {p['age']} {p['city']} lang {p['primary_language']} pay {p['available_payment_method']} transport {p['primary_transport_mode']}")

if __name__ == "__main__":
    main()

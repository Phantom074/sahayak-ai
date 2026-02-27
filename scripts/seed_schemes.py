#!/usr/bin/env python3
"""
Seed script: loads initial government scheme data into DynamoDB and OpenSearch.
Run once on environment setup: python3 scripts/seed_schemes.py --env dev
"""
import boto3
import json
import argparse
import sys
from decimal import Decimal
from datetime import datetime

SCHEMES = [
    {
        "scheme_id": "PM-KISAN-2024",
        "sk": "VERSION#latest",
        "name_en": "PM Kisan Samman Nidhi",
        "name_hi": "प्रधानमंत्री किसान सम्मान निधि",
        "ministry": "Ministry of Agriculture & Farmers Welfare",
        "categories": ["agriculture", "income_support"],
        "benefit_amount": Decimal("6000"),
        "benefit_frequency": "annual",
        "eligible_states": ["ALL"],
        "eligible_occupations": ["farmer"],
        "eligibility_criteria": {
            "occupation": ["farmer"],
            "max_land_acres": Decimal("5"),
            "excluded_categories": ["government_employee", "income_taxpayer", "institutional_landholders"]
        },
        "required_documents": ["aadhaar", "bank_account", "land_records"],
        "application_url": "https://pmkisan.gov.in",
        "last_verified": "2024-01-10",
        "active": True,
        "description_en": "PM-KISAN provides income support of Rs 6000 per year to all land-holding farmer families in India. Amount is transferred directly to bank accounts in three equal installments of Rs 2000 each.",
        "description_hi": "पीएम-किसान योजना के तहत सभी भूमिधारी किसान परिवारों को प्रति वर्ष 6000 रुपये की आय सहायता दी जाती है।"
    },
    {
        "scheme_id": "PMAY-G-2024",
        "sk": "VERSION#latest",
        "name_en": "Pradhan Mantri Awaas Yojana - Gramin",
        "name_hi": "प्रधानमंत्री आवास योजना - ग्रामीण",
        "ministry": "Ministry of Rural Development",
        "categories": ["housing", "rural_development"],
        "benefit_amount": Decimal("120000"),
        "benefit_frequency": "one_time",
        "eligible_states": ["ALL"],
        "eligible_occupations": ["ALL"],
        "eligibility_criteria": {
            "housing_status": ["houseless", "kutcha_house"],
            "bpl_category": True,
            "excluded_categories": ["government_employee", "motorized_vehicle_owner"]
        },
        "required_documents": ["aadhaar", "bank_account", "bpl_card", "land_proof"],
        "application_url": "https://pmayg.nic.in",
        "last_verified": "2024-01-10",
        "active": True,
        "description_en": "PMAY-G provides financial assistance of Rs 1.20 lakh in plain areas and Rs 1.30 lakh in hilly/NE states for construction of pucca houses to eligible rural poor.",
        "description_hi": "पीएमएवाई-ग्रामीण के तहत पात्र ग्रामीण गरीबों को पक्का मकान बनाने के लिए 1.20 लाख रुपये की आर्थिक सहायता दी जाती है।"
    },
    {
        "scheme_id": "MGNREGS-2024",
        "sk": "VERSION#latest",
        "name_en": "Mahatma Gandhi NREGS",
        "name_hi": "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार गारंटी अधिनियम",
        "ministry": "Ministry of Rural Development",
        "categories": ["employment", "rural_development"],
        "benefit_amount": None,
        "benefit_frequency": "per_day",
        "eligible_states": ["ALL"],
        "eligible_occupations": ["ALL"],
        "eligibility_criteria": {
            "residence": ["rural"],
            "adult_willing_to_work": True,
        },
        "required_documents": ["aadhaar", "job_card", "bank_account"],
        "application_url": "https://nrega.nic.in",
        "last_verified": "2024-01-10",
        "active": True,
        "description_en": "MGNREGS guarantees 100 days of unskilled wage employment per year to every rural household whose adult members volunteer to do unskilled manual work.",
        "description_hi": "मनरेगा के तहत हर ग्रामीण परिवार के वयस्क सदस्यों को वर्ष में 100 दिन के अकुशल मजदूरी रोजगार की गारंटी है।"
    },
]

ELIGIBILITY_RULES = [
    {
        "scheme_id": "PM-KISAN-2024",
        "sk": "RULES#latest",
        "application_url": "https://pmkisan.gov.in",
        "required_documents": ["aadhaar", "bank_account", "land_records"],
        "criteria": [
            {"field": "occupation", "operator": "in", "value": ["farmer", "agriculture"], "weight": 2.5, "message_hi_pass": "आप किसान हैं", "message_hi_fail": "यह योजना केवल किसानों के लिए है", "message_en_pass": "You are a farmer", "message_en_fail": "This scheme is only for farmers"},
            {"field": "annual_income", "operator": "lte", "value": 200000, "weight": 1.0, "message_hi_pass": "आय पात्रता सीमा के अंदर है", "message_hi_fail": "वार्षिक आय बहुत अधिक है", "message_en_pass": "Income within limit", "message_en_fail": "Annual income too high"},
            {"field": "land_holdings_acres", "operator": "between", "value": [0.1, 5.0], "weight": 2.0, "message_hi_pass": "भूमि जोत पात्र है", "message_hi_fail": "भूमि जोत सीमा से बाहर है", "message_en_pass": "Land holding eligible", "message_en_fail": "Land holding out of range"},
        ]
    },
    {
        "scheme_id": "MGNREGS-2024",
        "sk": "RULES#latest",
        "application_url": "https://nrega.nic.in",
        "required_documents": ["aadhaar", "job_card", "bank_account"],
        "criteria": [
            {"field": "age", "operator": "gte", "value": 18, "weight": 2.0, "message_hi_pass": "आयु पात्र है", "message_hi_fail": "18 वर्ष से कम आयु", "message_en_pass": "Age eligible", "message_en_fail": "Below 18 years"},
        ]
    }
]


def seed(env: str):
    dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
    
    schemes_table = dynamodb.Table(f"sahayak-{env}-schemes")
    rules_table = dynamodb.Table(f"sahayak-{env}-eligibility-rules")

    print(f"Seeding schemes into sahayak-{env}-schemes...")
    for scheme in SCHEMES:
        schemes_table.put_item(Item={**scheme, "seeded_at": datetime.utcnow().isoformat()})
        print(f"  Seeded: {scheme['scheme_id']}")

    print(f"Seeding eligibility rules into sahayak-{env}-eligibility-rules...")
    for rules in ELIGIBILITY_RULES:
        rules_table.put_item(Item={**rules, "seeded_at": datetime.utcnow().isoformat()})
        print(f"  Seeded rules: {rules['scheme_id']}")

    print("Seeding complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev", choices=["dev", "staging", "prod"])
    args = parser.parse_args()
    
    if args.env == "prod":
        confirm = input("WARNING: Seeding PRODUCTION. Type 'yes' to confirm: ")
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)
    
    seed(args.env)

"""Tagging taxonomy for categorization."""

TAXONOMY = {
    "Work": {
        "Market": {
            "tags": ["#Market"],
            "keywords": ["market", "시장", "macro", "매크로", "economy", "경제", "금리", "interest rate", "inflation", "인플레이션"],
        },
        "Funding": {
            "tags": ["#Funding"],
            "keywords": ["funding", "펀딩", "fundraise", "LP", "투자자", "fund", "펀드", "AUM", "commitment"],
        },
        "NewDeal": {
            "tags": ["#NewDeal"],
            "keywords": ["new deal", "신규", "파이프라인", "pipeline", "소싱", "sourcing", "deal flow", "투자검토", "HiT", "due diligence", "DD"],
        },
        "PostDeal": {
            "tags": ["#PostDeal"],
            "keywords": ["post deal", "포트폴리오", "portfolio", "모니터링", "monitoring", "밸류업", "value-up", "이사회", "board"],
        },
        "Exit": {
            "tags": ["#Exit"],
            "keywords": ["exit", "엑싯", "IPO", "M&A", "매각", "회수", "secondary", "세컨더리"],
        },
    },
    "Personal": {
        "Investment": {
            "tags": ["#개인투자"],
            "keywords": ["개인투자", "주식", "stock", "crypto", "코인", "부동산", "real estate", "자산"],
        },
        "Health": {
            "tags": ["#건강"],
            "keywords": ["건강", "health", "운동", "exercise", "수면", "sleep", "식단", "diet", "명상", "meditation"],
        },
        "Philosophy": {
            "tags": ["#철학"],
            "keywords": ["철학", "philosophy", "의미", "meaning", "가치", "value", "삶", "life", "성찰", "reflection"],
        },
    },
}

CATEGORY_MAP = {
    "Market": "Work/Market",
    "Funding": "Work/Funding",
    "NewDeal": "Work/NewDeal",
    "PostDeal": "Work/PostDeal",
    "Exit": "Work/Exit",
    "Investment": "Personal/Investment",
    "Health": "Personal/Health",
    "Philosophy": "Personal/Philosophy",
}

"""
eval_data/dataset.py
====================
Phase 4: Synthetic evaluation dataset — 25 resumes with known ground truth.

NO real personal information is used.
Each entry has:
  - id:       unique slug
  - text:     the resume as plain text
  - expected: ground-truth dict matching CandidateRecord fields
  - notes:    short description of what this case tests

Loaded by scripts/evaluate_extraction.py.
"""

from __future__ import annotations

DATASET: list[dict] = [

    # ------------------------------------------------------------------ #
    # 1. Clean, well-structured senior engineer resume
    # ------------------------------------------------------------------ #
    {
        "id": "R01_senior_engineer",
        "notes": "Standard well-structured resume; all fields present",
        "text": """
Alice Johnson
alice.johnson@techcorp.com | +1 (650) 555-0101 | Palo Alto, CA
https://linkedin.com/in/alicejohnson | https://github.com/alicejohnson

SUMMARY
Senior Software Engineer, 6 years in distributed systems.

EDUCATION
M.Sc. Computer Science — Stanford University, 2018
B.Sc. Computer Engineering — UC Berkeley, 2016

TECHNICAL SKILLS
Python, Go, Rust, Java, JavaScript

TOOLS & PLATFORMS
Kubernetes, Docker, AWS, GCP, Terraform, Kafka

EXPERIENCE
Senior Software Engineer — DistribCo (Mar 2020 – Present)
  • Led migration from monolith to microservices, reducing latency by 40%.
  • Managed a team of 5 engineers.

Software Engineer — StartupX (Jun 2018 – Feb 2020)
  • Built REST APIs serving 500K daily users.

PROJECTS
OpenTrace — Distributed tracing library (Go, gRPC, Prometheus)
DataPipe — Real-time ETL framework (Python, Kafka, Postgres)

CERTIFICATIONS
Google Cloud Professional Data Engineer (2022)
AWS Certified Solutions Architect Associate (2021)
""",
        "expected": {
            "full_name": "Alice Johnson",
            "email": "alice.johnson@techcorp.com",
            "phone": "+1 (650) 555-0101",
            "location": "Palo Alto, CA",
            "education_count": 2,
            "graduation_years": ["2018", "2016"],
            "has_technical_skills": True,
            "work_experience_count": 2,
            "project_count": 2,
            "certification_count": 2,
            "linkedin_url_present": True,
            "github_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 2. Indian developer — Indian phone format, no GitHub
    # ------------------------------------------------------------------ #
    {
        "id": "R02_indian_developer",
        "notes": "Indian format phone, single degree, single job",
        "text": """
Ravi Kumar
ravi.kumar@example.in | +91-99887-76655 | Bengaluru, India
linkedin.com/in/ravikumar99

EDUCATION
B.Tech Computer Science — IIT Madras, 2020

SKILLS
Java, Spring Boot, Python, MySQL, Redis, Docker

EXPERIENCE
Software Developer — Infosys Ltd (Aug 2020 – Present)
  • Developed REST APIs for banking clients.
  • Improved query performance by 30%.

PROJECTS
PayGateway — Payment processing microservice (Java, Spring Boot, MySQL)

CERTIFICATIONS
Oracle Certified Professional Java SE 11
""",
        "expected": {
            "full_name": "Ravi Kumar",
            "email": "ravi.kumar@example.in",
            "phone_digits_min": 10,
            "location": "Bengaluru, India",
            "education_count": 1,
            "graduation_years": ["2020"],
            "has_technical_skills": True,
            "work_experience_count": 1,
            "project_count": 1,
            "certification_count": 1,
            "linkedin_url_present": True,
            "github_url_present": False,
        },
    },

    # ------------------------------------------------------------------ #
    # 3. Fresher — no work experience
    # ------------------------------------------------------------------ #
    {
        "id": "R03_fresher_no_experience",
        "notes": "Fresh graduate, no work experience section",
        "text": """
Priya Sharma
priya.sharma@gmail.com | 9876543210 | Hyderabad, India

EDUCATION
B.E. Electronics and Communication — Osmania University, Expected 2025

SKILLS
C, C++, Embedded Systems, RTOS, PCB Design

PROJECTS
Smart Irrigation System — Arduino-based automated irrigation (C, Sensors)
Attendance Tracker — RFID-based attendance system (C++, RFID)

CERTIFICATIONS
NPTEL: Introduction to Internet of Things (2024)
""",
        "expected": {
            "full_name": "Priya Sharma",
            "email": "priya.sharma@gmail.com",
            "phone_digits_min": 10,
            "education_count": 1,
            "graduation_years": ["2025"],
            "has_technical_skills": True,
            "work_experience_count": 0,
            "project_count": 2,
            "certification_count": 1,
            "linkedin_url_present": False,
            "github_url_present": False,
        },
    },

    # ------------------------------------------------------------------ #
    # 4. No email — email must not be invented
    # ------------------------------------------------------------------ #
    {
        "id": "R04_no_email",
        "notes": "Email absent — model must return null, not invent one",
        "text": """
John Smith
New York, NY | +1 212-555-0191

EDUCATION
B.Sc. Applied Mathematics — New York University, 2019

SKILLS
R, Python, MATLAB, Statistics

EXPERIENCE
Data Analyst — FinanceHouse LLC (Jan 2020 – Present)
  • Built predictive models for credit risk.

PROJECTS
CreditScore — Credit risk modelling pipeline (Python, scikit-learn)
""",
        "expected": {
            "full_name": "John Smith",
            "email": None,
            "location": "New York, NY",
            "education_count": 1,
            "work_experience_count": 1,
            "project_count": 1,
            "linkedin_url_present": False,
        },
    },

    # ------------------------------------------------------------------ #
    # 5. No phone — phone must not be invented
    # ------------------------------------------------------------------ #
    {
        "id": "R05_no_phone",
        "notes": "Phone absent — model must return null",
        "text": """
Maria Rossi
maria.rossi@designco.it | Milan, Italy
https://linkedin.com/in/mariarossi

EDUCATION
M.A. Interaction Design — Politecnico di Milano, 2021

SKILLS
Figma, Sketch, Adobe XD, HTML, CSS

EXPERIENCE
UX Designer — DesignCo (Mar 2021 – Present)
  • Led user research for 3 mobile products.

PROJECTS
BankingApp — Redesigned banking app UX (Figma, Prototyping)
""",
        "expected": {
            "full_name": "Maria Rossi",
            "email": "maria.rossi@designco.it",
            "phone": None,
            "location": "Milan, Italy",
            "education_count": 1,
            "work_experience_count": 1,
            "linkedin_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 6. Multiple education records
    # ------------------------------------------------------------------ #
    {
        "id": "R06_multiple_education",
        "notes": "Three education records — all must be captured",
        "text": """
David Chen
david.chen@academia.edu | +1 617-555-0182 | Boston, MA
https://github.com/davidchen

EDUCATION
Ph.D. Machine Learning — MIT, 2023
M.Sc. Computer Science — Carnegie Mellon University, 2019
B.Sc. Mathematics — University of Toronto, 2017

RESEARCH SKILLS
PyTorch, TensorFlow, CUDA, Python, R, C++

EXPERIENCE
Research Scientist — DeepLearn Inc (Jul 2023 – Present)
  • Published 3 papers on transformer efficiency.

PUBLICATIONS
"Efficient Attention Mechanisms", NeurIPS 2022
""",
        "expected": {
            "full_name": "David Chen",
            "email": "david.chen@academia.edu",
            "education_count": 3,
            "graduation_years": ["2023", "2019", "2017"],
            "work_experience_count": 1,
            "github_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 7. Long skills list
    # ------------------------------------------------------------------ #
    {
        "id": "R07_long_skills_list",
        "notes": "Unusually long skills section — must not be truncated",
        "text": """
Sam Rivera
sam.rivera@devops.io | +1 503-555-0177 | Portland, OR
https://linkedin.com/in/samrivera | https://github.com/samrivera

EDUCATION
B.Sc. Computer Science — Oregon State University, 2018

TECHNICAL SKILLS
Python, Go, Bash, Ruby, Perl, Scala, Kotlin, TypeScript, JavaScript, Java, C, C++,
Rust, Lua, Haskell, Elixir, Clojure, Swift, R, MATLAB, Julia, Dart, PHP

DEVOPS & CLOUD
AWS, GCP, Azure, Kubernetes, Docker, Helm, Terraform, Ansible, Puppet, Chef,
Jenkins, CircleCI, GitHub Actions, ArgoCD, Flux, Vault, Consul, Nomad

EXPERIENCE
Senior DevOps Engineer — MegaCorp (Feb 2020 – Present)
  • Managed 500-node Kubernetes cluster.
  • Automated CI/CD for 80 microservices.

DevOps Engineer — SmallStartup (Jun 2018 – Jan 2020)
  • Built AWS infrastructure from scratch.
""",
        "expected": {
            "full_name": "Sam Rivera",
            "email": "sam.rivera@devops.io",
            "has_technical_skills": True,
            "skills_count_min": 10,
            "work_experience_count": 2,
            "linkedin_url_present": True,
            "github_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 8. Ambiguous dates
    # ------------------------------------------------------------------ #
    {
        "id": "R08_ambiguous_dates",
        "notes": "Dates in varied formats — must be preserved as text",
        "text": """
Fatima Al-Rashid
fatima@example.com | +971-50-555-0133 | Dubai, UAE

EDUCATION
MBA — American University of Dubai, Sept 2018 – Aug 2020
B.B.A. Finance — UAE University, 2014-2018

EXPERIENCE
Finance Manager — GlobalBank UAE (Q3 2020 – Present)
  • Managed $50M loan portfolio.

Junior Analyst — CapitalFirm (2015/06 – 2018/08)
  • Prepared investment reports.
""",
        "expected": {
            "full_name": "Fatima Al-Rashid",
            "email": "fatima@example.com",
            "education_count": 2,
            "work_experience_count": 2,
            "location": "Dubai, UAE",
        },
    },

    # ------------------------------------------------------------------ #
    # 9. Minimal resume — almost no information
    # ------------------------------------------------------------------ #
    {
        "id": "R09_minimal_resume",
        "notes": "Nearly empty resume — most fields should be null/empty",
        "text": """
Alex Ng
Backend Developer

SKILLS
Node.js, Express, MongoDB
""",
        "expected": {
            "full_name": "Alex Ng",
            "email": None,
            "phone": None,
            "education_count": 0,
            "work_experience_count": 0,
            "has_technical_skills": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 10. Non-standard section headings
    # ------------------------------------------------------------------ #
    {
        "id": "R10_nonstandard_headings",
        "notes": "Unusual section headings — model must still parse correctly",
        "text": """
Carlos Mendez
carlos.mendez@startuplab.mx | +52-55-5555-0144 | Mexico City, Mexico
https://github.com/carlosmendez

What I Know
Python, Django, React, PostgreSQL, Redis

Where I Studied
B.Sc. Software Engineering — UNAM, Mexico City, 2017

Where I Worked
Full-Stack Developer — LabMex (Mar 2017 – Dec 2019)
  • Built e-commerce platform for 10K users.

Tech Lead — PixelFactory (Jan 2020 – Present)
  • Led team of 6 developers.

Things I Built
MexShop — E-commerce platform (Django, React, PostgreSQL)
LabDash — Internal analytics dashboard (Python, Pandas)
""",
        "expected": {
            "full_name": "Carlos Mendez",
            "email": "carlos.mendez@startuplab.mx",
            "education_count": 1,
            "graduation_years": ["2017"],
            "work_experience_count": 2,
            "project_count": 2,
            "github_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 11. Candidate with GitHub only (no LinkedIn)
    # ------------------------------------------------------------------ #
    {
        "id": "R11_github_only",
        "notes": "GitHub present, LinkedIn absent",
        "text": """
Lena Fischer
lena.fischer@code.de | +49-30-5550182 | Berlin, Germany
https://github.com/lenafischer

EDUCATION
B.Sc. Computer Science — TU Berlin, 2020

SKILLS
C++, Python, OpenCV, ROS, SLAM, Embedded Linux

EXPERIENCE
Robotics Engineer — RoboLab GmbH (Aug 2020 – Present)
  • Developed autonomous navigation stack for industrial robots.
""",
        "expected": {
            "full_name": "Lena Fischer",
            "email": "lena.fischer@code.de",
            "github_url_present": True,
            "linkedin_url_present": False,
            "education_count": 1,
            "work_experience_count": 1,
        },
    },

    # ------------------------------------------------------------------ #
    # 12. Multiple projects with technologies
    # ------------------------------------------------------------------ #
    {
        "id": "R12_many_projects",
        "notes": "Five projects — all should be captured",
        "text": """
Akira Tanaka
akira.tanaka@devmail.jp | +81-3-5550-1982 | Tokyo, Japan
https://linkedin.com/in/akiratanaka

EDUCATION
B.Eng. Information Systems — Waseda University, 2021

SKILLS
Python, JavaScript, React, Node.js, MongoDB

PROJECTS
EchoChat — Real-time messaging app (React, Node.js, Socket.IO)
WeatherNow — Weather forecast API wrapper (Python, FastAPI)
StudyBuddy — Online study group platform (React, MongoDB)
TravelLog — Travel journal web app (JavaScript, LocalStorage)
CodeReview — Peer code review tool (Python, Flask, PostgreSQL)

EXPERIENCE
Junior Developer — TechTokyo Inc (Apr 2021 – Present)
  • Shipped 3 production features for enterprise SaaS.
""",
        "expected": {
            "full_name": "Akira Tanaka",
            "email": "akira.tanaka@devmail.jp",
            "education_count": 1,
            "work_experience_count": 1,
            "project_count": 5,
            "has_technical_skills": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 13. Multiple certifications
    # ------------------------------------------------------------------ #
    {
        "id": "R13_many_certifications",
        "notes": "Six certifications — all should be listed",
        "text": """
Ndidi Okafor
ndidi.okafor@cloud.ng | +234-806-555-0173 | Lagos, Nigeria
https://linkedin.com/in/ndidiokafor

EDUCATION
B.Sc. Computer Science — University of Lagos, 2018

SKILLS
AWS, Azure, GCP, Terraform, Python, Linux

EXPERIENCE
Cloud Engineer — AfriCloud (Jan 2019 – Present)
  • Architected multi-cloud infrastructure for fintech clients.

CERTIFICATIONS
AWS Solutions Architect – Professional (2023)
AWS DevOps Engineer – Professional (2022)
Azure Solutions Architect Expert (2022)
GCP Professional Cloud Architect (2021)
Terraform Associate (2021)
Linux Foundation Certified System Administrator (2020)
""",
        "expected": {
            "full_name": "Ndidi Okafor",
            "email": "ndidi.okafor@cloud.ng",
            "education_count": 1,
            "work_experience_count": 1,
            "certification_count": 6,
        },
    },

    # ------------------------------------------------------------------ #
    # 14. Career changer — education in different field
    # ------------------------------------------------------------------ #
    {
        "id": "R14_career_changer",
        "notes": "Degree in non-CS field, career change to data science",
        "text": """
Sophie Laurent
sophie.laurent@datawiz.fr | +33-1-5550-1844 | Paris, France
https://linkedin.com/in/sophielaurent

EDUCATION
M.Sc. Economics — Paris School of Economics, 2016
B.Sc. Mathematics — Université Paris-Sud, 2014

CAREER TRANSITION TRAINING
Data Science Bootcamp — Le Wagon Paris, 2018

SKILLS
Python, R, SQL, Tableau, Power BI, Machine Learning, Statistics

EXPERIENCE
Data Scientist — EconData Analytics (Sep 2018 – Present)
  • Built demand forecasting models that improved inventory accuracy by 22%.

Economist — French Ministry of Finance (Sep 2016 – Aug 2018)
  • Produced policy research on labour markets.
""",
        "expected": {
            "full_name": "Sophie Laurent",
            "email": "sophie.laurent@datawiz.fr",
            "education_count_min": 2,
            "work_experience_count": 2,
            "has_technical_skills": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 15. Senior manager — no GitHub, portfolio URL present
    # ------------------------------------------------------------------ #
    {
        "id": "R15_senior_manager",
        "notes": "No GitHub, has portfolio URL, senior management role",
        "text": """
Michael Thompson
m.thompson@consultancy.co.uk | +44-20-5550-1933 | London, UK
https://linkedin.com/in/michaelthompson | https://mthompson.co.uk

EDUCATION
MBA — London Business School, 2012
B.Sc. Computer Science — University of Manchester, 2008

SKILLS
Leadership, Agile, Scrum, Product Strategy, Stakeholder Management,
SQL, Python (basic), Tableau

EXPERIENCE
VP of Engineering — FinServ UK (Mar 2019 – Present)
  • Led 60-person engineering org across 4 countries.

Engineering Manager — RetailTech (Jan 2015 – Feb 2019)
  • Shipped 2 major platform releases.

Senior Engineer — CodeHouse (Jul 2012 – Dec 2014)
  • Developed payment processing systems.
""",
        "expected": {
            "full_name": "Michael Thompson",
            "email": "m.thompson@consultancy.co.uk",
            "linkedin_url_present": True,
            "portfolio_url_present": True,
            "github_url_present": False,
            "education_count": 2,
            "work_experience_count": 3,
        },
    },

    # ------------------------------------------------------------------ #
    # 16. Completely empty skills section
    # ------------------------------------------------------------------ #
    {
        "id": "R16_no_skills_section",
        "notes": "No explicit skills section — skills should be empty or extracted from context",
        "text": """
Roberto Bianchi
roberto.bianchi@law.it | +39-02-5550-1711 | Rome, Italy

EDUCATION
J.D. Law — Sapienza University of Rome, 2015

EXPERIENCE
Associate Lawyer — Studio Legale ABC (Sep 2015 – Present)
  • Specialised in corporate and contract law.
  • Handled 50+ M&A transactions.

Junior Lawyer — Rome Legal Partners (Jun 2013 – Aug 2015)
  • Drafted contracts and handled litigation support.
""",
        "expected": {
            "full_name": "Roberto Bianchi",
            "email": "roberto.bianchi@law.it",
            "education_count": 1,
            "work_experience_count": 2,
        },
    },

    # ------------------------------------------------------------------ #
    # 17. Short one-page resume, all on one block
    # ------------------------------------------------------------------ #
    {
        "id": "R17_compact_onepage",
        "notes": "Dense, compact single-block format",
        "text": """Yuki Park | yuki.park@email.com | +82-10-5555-0166 | Seoul, South Korea
B.Sc. Computer Engineering — KAIST 2022 | Skills: Python, C, Java, Spring, React, MySQL
Experience: Software Engineer at KoreaTech (Jul 2022 – Present): REST API development, CI/CD setup
Project: FoodDeliveryApp — Food delivery platform (Java, Spring, MySQL)
Certifications: AWS Cloud Practitioner (2023)""",
        "expected": {
            "full_name": "Yuki Park",
            "email": "yuki.park@email.com",
            "education_count": 1,
            "graduation_years": ["2022"],
            "work_experience_count": 1,
            "project_count": 1,
        },
    },

    # ------------------------------------------------------------------ #
    # 18. PhD academic with publications (no standard "Projects")
    # ------------------------------------------------------------------ #
    {
        "id": "R18_academic_phd",
        "notes": "Academic CV format, publications instead of projects",
        "text": """
Dr. Aarav Mehta
aarav.mehta@iitb.ac.in | +91-22-5550-1944 | Mumbai, India
https://linkedin.com/in/aaravmehta

EDUCATION
Ph.D. Electrical Engineering — IIT Bombay, 2022
M.Tech. Signal Processing — IIT Delhi, 2017
B.Tech. Electronics — NIT Trichy, 2015

RESEARCH INTERESTS
Deep Learning, Signal Processing, Computer Vision

SKILLS
Python, MATLAB, TensorFlow, PyTorch, OpenCV, C++

EXPERIENCE
Postdoctoral Researcher — IIT Bombay (Jul 2022 – Present)

PUBLICATIONS
"Attention-Based Signal Classification", IEEE Transactions 2023
"Sparse Signal Recovery via Deep Networks", NeurIPS 2021
""",
        "expected": {
            "full_name": "Dr. Aarav Mehta",
            "email": "aarav.mehta@iitb.ac.in",
            "education_count": 3,
            "graduation_years": ["2022", "2017", "2015"],
            "work_experience_count": 1,
            "has_technical_skills": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 19. Gaps in employment history
    # ------------------------------------------------------------------ #
    {
        "id": "R19_employment_gaps",
        "notes": "Visible gaps between jobs, career break",
        "text": """
Emma Wilson
emma.wilson@freelance.nz | +64-9-5550-1822 | Auckland, New Zealand
https://linkedin.com/in/emmawilsonnz

EDUCATION
B.A. Graphic Design — Auckland University of Technology, 2014

SKILLS
Adobe Illustrator, Photoshop, InDesign, Figma, HTML, CSS

EXPERIENCE
Senior Designer — AgencyNZ (Feb 2021 – Present)
  • Led brand identity projects for 10 clients.

Freelance Designer — Self-employed (Jan 2017 – Dec 2020)
  • Worked with 30+ clients across APAC.

Junior Designer — CreativeStudio Auckland (Mar 2015 – Nov 2016)
  • Produced print and digital marketing materials.
""",
        "expected": {
            "full_name": "Emma Wilson",
            "email": "emma.wilson@freelance.nz",
            "education_count": 1,
            "work_experience_count": 3,
            "linkedin_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 20. Formula injection attempt in name field
    # ------------------------------------------------------------------ #
    {
        "id": "R20_formula_injection",
        "notes": "Suspicious strings in various fields — injection must be sanitised at export",
        "text": """
=SUM(A1:A100)
injection.test@example.com | +1-555-0100 | Anywhere, USA

EDUCATION
B.Sc. Computer Science — State University, 2020

SKILLS
Python, Hacking, SQL Injection, XSS

EXPERIENCE
Security Researcher — CyberCo (2020 – Present)
  • Performed penetration testing.
""",
        "expected": {
            "email": "injection.test@example.com",
            "education_count": 1,
            "work_experience_count": 1,
        },
    },

    # ------------------------------------------------------------------ #
    # 21. Two-digit graduation year (should not match as 4-digit year)
    # ------------------------------------------------------------------ #
    {
        "id": "R21_short_year",
        "notes": "Graduation year written as 2-digit — model must handle gracefully",
        "text": """
Lin Wei
lin.wei@techuni.cn | +86-10-5550-1988 | Beijing, China

EDUCATION
B.Eng. Software Engineering — Tsinghua University, '22

SKILLS
Java, Spring Boot, Microservices, Kafka, MySQL

EXPERIENCE
Software Engineer — ByteDance (Jul 2022 – Present)
  • Developed high-performance recommendation engine.
""",
        "expected": {
            "full_name": "Lin Wei",
            "email": "lin.wei@techuni.cn",
            "education_count": 1,
            "work_experience_count": 1,
        },
    },

    # ------------------------------------------------------------------ #
    # 22. Remote-first candidate — no location
    # ------------------------------------------------------------------ #
    {
        "id": "R22_no_location",
        "notes": "No location specified — location should be null",
        "text": """
Omar Khalid
omar.khalid@remotedev.io | +973-3-5550199
https://github.com/omarkhalid

EDUCATION
B.Sc. Information Systems — University of Bahrain, 2019

SKILLS
React, TypeScript, Node.js, GraphQL, PostgreSQL

EXPERIENCE
Remote Full-Stack Developer — USStartup (Apr 2020 – Present)
  • Built user-facing features for 100K+ user SaaS platform.

PROJECTS
TodoFlow — Task management app (React, Node.js, MongoDB)
""",
        "expected": {
            "full_name": "Omar Khalid",
            "email": "omar.khalid@remotedev.io",
            "location": None,
            "education_count": 1,
            "work_experience_count": 1,
            "project_count": 1,
            "github_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 23. Internship only — no full-time experience
    # ------------------------------------------------------------------ #
    {
        "id": "R23_intern_only",
        "notes": "Only internship experience, student currently enrolled",
        "text": """
Amara Diallo
amara.diallo@student.edu | +221-77-555-0121 | Dakar, Senegal

EDUCATION
B.Sc. Computer Science — Université Cheikh Anta Diop, Expected 2026

SKILLS
Python, JavaScript, HTML, CSS, Git

INTERNSHIP EXPERIENCE
Software Intern — AfriTech Solutions (Jul 2024 – Sep 2024)
  • Built internal dashboard for HR team.
  • Worked with React and Django.

PROJECTS
LibrarySystem — Library management system (Python, Django, SQLite)
""",
        "expected": {
            "full_name": "Amara Diallo",
            "email": "amara.diallo@student.edu",
            "education_count": 1,
            "graduation_years": ["2026"],
            "work_experience_count": 1,
            "project_count": 1,
        },
    },

    # ------------------------------------------------------------------ #
    # 24. Very long work experience section (6 jobs)
    # ------------------------------------------------------------------ #
    {
        "id": "R24_long_experience",
        "notes": "Six jobs over 18 years — all should be captured",
        "text": """
James O'Brien
james.obrien@techvp.ie | +353-1-555-0188 | Dublin, Ireland
https://linkedin.com/in/jamesobrien

EDUCATION
B.Sc. Computer Science — Trinity College Dublin, 2005

SKILLS
Java, Python, Scala, AWS, Architecture, Leadership

EXPERIENCE
CTO — IrishSaaS (Jan 2022 – Present)
  • Led company to $5M ARR.

VP Engineering — EuroCo (Feb 2018 – Dec 2021)
  • Scaled engineering team from 10 to 60.

Engineering Director — UKTech (Mar 2014 – Jan 2018)
  • Owned platform architecture.

Senior Engineer — LondonStartup (Jun 2010 – Feb 2014)
  • Core backend engineer.

Software Engineer — DublinDev (Jan 2008 – May 2010)
  • Full-stack web development.

Junior Developer — CodeIreland (Jun 2005 – Dec 2007)
  • Entry-level software role.
""",
        "expected": {
            "full_name": "James O'Brien",
            "email": "james.obrien@techvp.ie",
            "education_count": 1,
            "work_experience_count": 6,
            "linkedin_url_present": True,
        },
    },

    # ------------------------------------------------------------------ #
    # 25. Mixed language content (non-ASCII name, English resume)
    # ------------------------------------------------------------------ #
    {
        "id": "R25_unicode_name",
        "notes": "Non-ASCII name — must be preserved exactly",
        "text": """
Müller, Björn
bjorn.muller@techgmbh.de | +49-89-5550-1744 | Munich, Germany
https://linkedin.com/in/bjornmuller | https://github.com/bjornmuller

EDUCATION
M.Sc. Informatik — Technische Universität München, 2019
B.Sc. Informatik — Universität Stuttgart, 2017

SKILLS
C++, Python, Rust, Qt, Embedded Linux, CAN Bus, AUTOSAR

EXPERIENCE
Embedded Software Engineer — AutoTech GmbH (Sep 2019 – Present)
  • Developed real-time control systems for automotive ECUs.

CERTIFICATIONS
AUTOSAR Classic Platform Developer (2021)
""",
        "expected": {
            "email": "bjorn.muller@techgmbh.de",
            "education_count": 2,
            "graduation_years": ["2019", "2017"],
            "work_experience_count": 1,
            "certification_count": 1,
            "linkedin_url_present": True,
            "github_url_present": True,
        },
    },
]

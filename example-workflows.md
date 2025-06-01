# SueChef + Claude Desktop Example Workflows

Real-world examples of how to use SueChef with Claude Desktop for legal research and case management.

## 🏠 Premises Liability Case Workflow

**Scenario**: Water damage case against landlord, need to build timeline and find precedents.

### Step 1: Initial Case Setup
```
I'm starting a new premises liability case. Can you help me set up the case in SueChef?

Case details:
- Tenant: Jane Smith  
- Property: 123 Oak Street, Apartment 4B
- Landlord: ABC Property Management
- Issue: Ceiling leak causing water damage
- Initial incident: May 14, 2023
```

**Claude's Response**: Uses `add_event` to create initial timeline entry with proper legal context.

### Step 2: Timeline Development
```
Let's build a complete timeline. Add these additional events:

1. May 16, 2023: Tenant reports leak to property manager via email
2. May 18, 2023: Property manager acknowledges receipt, promises repair "soon"
3. June 1, 2023: No repairs made, tenant sends certified letter
4. June 15, 2023: Leak worsens, causing damage to tenant's furniture
5. July 1, 2023: Tenant withholds rent, cites habitability issues
```

**Claude's Response**: Uses multiple `add_event` calls with proper party identification and significance ranking.

### Step 3: Legal Research
```
Now let's research relevant precedents. Search for cases involving:
- Landlord duty to repair
- Notice requirements for habitability issues  
- Tenant remedies for water damage
- Rent withholding rights

Focus on California law if possible.
```

**Claude's Response**: Uses `search_courtlistener_opinions` and `unified_legal_search` to find relevant precedents.

### Step 4: Precedent Analysis
```
From the search results, import the most relevant 3-5 cases as legal snippets. For each one, create a snippet that captures:
- The key legal holding
- How it applies to our facts
- Whether it's binding or persuasive authority
```

**Claude's Response**: Uses `import_courtlistener_opinion` and `create_snippet` to build precedent database.

### Step 5: Strategy Development
```
Based on the timeline and precedents, analyze:
- What are our strongest legal arguments?
- What are potential weaknesses?
- What additional evidence should we gather?
- What are the likely damages we can recover?
```

**Claude's Response**: Uses `get_legal_analytics` and `temporal_legal_query` to provide strategic analysis.

## 📋 Contract Review Workflow

**Scenario**: Commercial lease review for restaurant client.

### Step 1: Document Analysis
```
I need to review a commercial lease agreement for a restaurant client. Can you help me set up a systematic review process using SueChef?

The lease is for a 2,500 sq ft space in downtown for a new Italian restaurant. 5-year term with renewal options.
```

### Step 2: Key Terms Timeline
```
As I review the lease, help me create timeline events for all critical dates:
- Lease commencement: March 1, 2024
- Rent escalation dates: March 1 of each year
- Option to renew deadline: September 1, 2028 (6 months before expiration)
- Required improvements completion: February 15, 2024
```

### Step 3: Risk Analysis Research
```
Research common issues in commercial restaurant leases:
- Assignment and subletting restrictions
- Use clause limitations  
- Common area maintenance (CAM) disputes
- Personal guarantee requirements
- Default and cure provisions
```

### Step 4: Precedent Review
```
Find recent cases involving:
- Restaurant lease disputes
- CAM charge disputes in commercial leases
- Personal guarantee enforcement
- Assignment rights for restaurant tenants
```

### Step 5: Client Advisory Memo
```
Based on the research and timeline, help me draft key points for a client advisory memo about:
- Major risk areas in this lease
- Recommended negotiation points
- Important compliance deadlines
- Suggested protective language
```

## ⚖️ Litigation Strategy Workflow

**Scenario**: Employment discrimination case preparation.

### Step 1: Case Chronology
```
I'm preparing an employment discrimination case. Help me build a detailed chronology:

Employee: Maria Rodriguez, hired January 15, 2020 as marketing coordinator
Issues began around June 2022 when new supervisor hired
Termination: March 3, 2023 (stated reason: "performance issues")
```

### Step 2: Evidence Timeline
```
Add these evidence-related events to build our discrimination timeline:

- June 15, 2022: New supervisor makes comment about "cultural fit"
- August 3, 2022: First negative performance review (previous reviews were positive)
- September 10, 2022: Employee files internal complaint with HR
- October 1, 2022: Employee receives written warning
- November 15, 2022: Employee files EEOC charge
- January 20, 2023: EEOC issues right to sue letter
- March 3, 2023: Termination occurs
```

### Step 3: Legal Standard Research
```
Research the current legal standards for:
- Discrimination based on national origin
- Retaliation for filing EEOC charges
- Pretext analysis in wrongful termination
- Damages available in employment discrimination cases

Focus on recent Ninth Circuit decisions.
```

### Step 4: Comparative Case Analysis
```
Find cases with similar fact patterns:
- Employees terminated shortly after filing EEOC charges
- "Cultural fit" comments as evidence of bias
- Performance review changes following discrimination complaints
- Cases involving Latino/Hispanic employees in marketing roles
```

### Step 5: Damages Calculation
```
Help me analyze potential damages by researching:
- Back pay calculation methods
- Front pay awards in similar cases
- Emotional distress damages in employment cases
- Attorney fee awards under employment discrimination statutes
```

## 🔍 Legal Research Deep Dive

**Scenario**: Novel legal issue requiring comprehensive research.

### Step 1: Issue Identification
```
I have a novel question about cryptocurrency and employment law: Can an employer legally require employees to accept cryptocurrency as payment for wages?

This involves intersection of:
- Wage and hour law
- Cryptocurrency regulation
- Employment contract law
- State vs. federal jurisdiction
```

### Step 2: Multi-Jurisdictional Research
```
Let's research this systematically across jurisdictions:

1. Federal law: Fair Labor Standards Act wage payment requirements
2. California law: Labor Code wage payment provisions  
3. Recent cryptocurrency regulations from DOL, IRS, SEC
4. Any existing cases involving cryptocurrency and employment
```

### Step 3: Temporal Analysis
```
Use SueChef's temporal analysis to understand how this area of law has evolved:
- Traditional wage payment requirements (historical)
- Early cryptocurrency adoption (2010-2015)
- Regulatory developments (2016-2020)
- Recent enforcement and litigation (2021-2024)
```

### Step 4: Community Detection
```
Use SueChef's community detection to find related legal concepts and unexplored angles:
- What other employment law issues intersect with cryptocurrency?
- Are there patterns in how courts handle novel payment methods?
- What regulatory trends might affect this analysis?
```

### Step 5: Predictive Analysis
```
Based on the research, help me predict:
- How courts are likely to rule on this issue
- What regulatory changes might be coming
- How to advise clients considering cryptocurrency payments
- What compliance measures would be prudent
```

## 📊 Legal Analytics Workflow

**Scenario**: Law firm wants to analyze their case outcomes and research patterns.

### Step 1: Data Aggregation
```
Our firm wants to analyze our legal research patterns and case outcomes. Can you help us use SueChef's analytics to understand:

- Which types of cases we research most often
- Our most frequently cited precedents
- Research patterns that correlate with successful outcomes
- Areas where we might be missing key precedents
```

### Step 2: Precedent Analysis
```
Analyze our precedent usage:
- Which cases do we cite most frequently?
- Are we relying too heavily on older precedents?
- What recent cases might strengthen our arguments?
- Which courts' decisions do we cite most often?
```

### Step 3: Research Efficiency
```
Help us optimize our research process:
- What search terms are most effective?
- Which databases provide the best results?
- How can we better organize our precedent library?
- What research gaps should we address?
```

### Step 4: Competitive Analysis
```
Use SueChef's community detection to understand:
- What legal concepts are other firms researching?
- Are there emerging areas of law we should monitor?
- What precedents are gaining attention in our practice areas?
```

## 🚀 Advanced Integration Examples

### Workflow Automation
```
Can you create a repeatable workflow for personal injury case setup that:
1. Creates standard timeline events (incident, medical treatment, demand)
2. Searches for similar cases in our jurisdiction
3. Identifies relevant medical malpractice or product liability precedents
4. Sets up analytics tracking for case development
```

### Multi-Matter Management
```
I'm working on three related cases involving the same defendant. Can you:
1. Set up separate group IDs for each case
2. Cross-reference common precedents across all three
3. Identify patterns that might support a coordinated strategy
4. Track research developments that affect all three matters
```

### Client Reporting
```
Generate a monthly research summary for our biggest client that includes:
- New precedents discovered in their industry
- Regulatory changes affecting their business
- Litigation trends in their sector
- Recommended compliance updates
```

---

These workflows demonstrate how SueChef transforms Claude Desktop into a powerful legal research and case management platform, enabling lawyers to work more efficiently and strategically! 🍳⚖️
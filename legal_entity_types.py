"""
Legal Entity Types for SueChef

Custom Pydantic models defining legal domain entities for use with Graphiti.
These types enable precise knowledge representation and automatic entity extraction.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Judge(BaseModel):
    """A judge presiding over legal proceedings"""
    name: str = Field(..., description="Full name of the judge")
    title: str | None = Field(None, description="Judicial title (e.g., Chief Judge, Associate Justice)")
    court: str | None = Field(None, description="Court where judge presides")
    appointment_date: str | None = Field(None, description="Date of judicial appointment")
    political_affiliation: str | None = Field(None, description="Political party affiliation")
    bar_admission: str | None = Field(None, description="State/jurisdiction of bar admission")


class Attorney(BaseModel):
    """A legal practitioner representing parties"""
    name: str = Field(..., description="Full name of the attorney")
    law_firm: str | None = Field(None, description="Name of law firm or organization")
    bar_number: str | None = Field(None, description="Bar registration number")
    specialization: str | None = Field(None, description="Primary area of legal practice")
    role: str | None = Field(None, description="Role in case (plaintiff counsel, defense counsel, etc.)")
    contact_info: str | None = Field(None, description="Contact information")


class Court(BaseModel):
    """A judicial court or tribunal"""
    name: str = Field(..., description="Full name of the court")
    abbreviation: str | None = Field(None, description="Standard court abbreviation")
    jurisdiction: str | None = Field(None, description="Geographic or subject matter jurisdiction")
    level: str | None = Field(None, description="Court level (trial, appellate, supreme)")
    location: str | None = Field(None, description="Physical location of court")
    circuit: str | None = Field(None, description="Circuit number for federal courts")


class LegalCase(BaseModel):
    """A legal case or proceeding"""
    case_name: str = Field(..., description="Full case name (e.g., Smith v. Jones)")
    case_number: str | None = Field(None, description="Docket or case number")
    court: str | None = Field(None, description="Court where case is filed")
    filing_date: str | None = Field(None, description="Date case was filed")
    case_type: str | None = Field(None, description="Type of case (civil, criminal, administrative)")
    status: str | None = Field(None, description="Current case status")
    subject_matter: str | None = Field(None, description="Primary legal issue or subject matter")


class Statute(BaseModel):
    """A law, regulation, or legal statute"""
    title: str = Field(..., description="Title or name of the statute")
    citation: str | None = Field(None, description="Legal citation (e.g., 42 U.S.C. § 1983)")
    jurisdiction: str | None = Field(None, description="Applicable jurisdiction")
    effective_date: str | None = Field(None, description="Date statute became effective")
    subject_area: str | None = Field(None, description="Area of law covered")
    summary: str | None = Field(None, description="Brief summary of statute's purpose")


class LegalPrecedent(BaseModel):
    """A legal precedent or case law"""
    citation: str = Field(..., description="Full legal citation")
    case_name: str | None = Field(None, description="Name of the precedent case")
    court: str | None = Field(None, description="Court that decided the case")
    decision_date: str | None = Field(None, description="Date of court decision")
    holding: str | None = Field(None, description="Legal holding or rule established")
    precedential_value: str | None = Field(None, description="Precedential weight (binding, persuasive)")
    overturned: bool | None = Field(None, description="Whether precedent has been overturned")


class LegalDocument(BaseModel):
    """A legal document or filing"""
    title: str = Field(..., description="Title or name of the document")
    document_type: str | None = Field(None, description="Type of document (brief, motion, order)")
    filing_date: str | None = Field(None, description="Date document was filed")
    author: str | None = Field(None, description="Author or drafter of document")
    case_relation: str | None = Field(None, description="Related case or proceeding")
    document_number: str | None = Field(None, description="Document number in case file")


class LegalEntity(BaseModel):
    """A legal entity or organization"""
    name: str = Field(..., description="Full name of the entity")
    entity_type: str | None = Field(None, description="Type of entity (corporation, partnership, LLC)")
    jurisdiction: str | None = Field(None, description="State or country of incorporation")
    business_type: str | None = Field(None, description="Primary business or industry")
    legal_status: str | None = Field(None, description="Current legal status")


class LegalProcedure(BaseModel):
    """A legal procedure or motion"""
    procedure_name: str = Field(..., description="Name of the legal procedure")
    procedure_type: str | None = Field(None, description="Type of procedure (motion, hearing, trial)")
    filing_requirements: str | None = Field(None, description="Required filings or documents")
    deadline: str | None = Field(None, description="Applicable deadline or time limit")
    court_rules: str | None = Field(None, description="Governing court rules or statutes")


class Expert(BaseModel):
    """An expert witness or consultant"""
    name: str = Field(..., description="Full name of the expert")
    credentials: str | None = Field(None, description="Professional credentials and qualifications")
    specialization: str | None = Field(None, description="Area of expertise")
    opinion_topic: str | None = Field(None, description="Topic of expert opinion")
    compensation: str | None = Field(None, description="Compensation or fee arrangement")


class Evidence(BaseModel):
    """A piece of evidence in legal proceedings"""
    description: str = Field(..., description="Description of the evidence")
    evidence_type: str | None = Field(None, description="Type of evidence (documentary, physical, testimonial)")
    source: str | None = Field(None, description="Source or origin of evidence")
    authentication: str | None = Field(None, description="Method of authentication")
    admissibility: str | None = Field(None, description="Admissibility status or concerns")
    exhibit_number: str | None = Field(None, description="Exhibit number if applicable")


class Claim(BaseModel):
    """A legal claim or cause of action"""
    claim_type: str = Field(..., description="Type of legal claim")
    elements: str | None = Field(None, description="Required elements to prove claim")
    damages_sought: str | None = Field(None, description="Type of damages or relief sought")
    statute_of_limitations: str | None = Field(None, description="Applicable statute of limitations")
    burden_of_proof: str | None = Field(None, description="Required burden of proof")


class Contract(BaseModel):
    """A legal contract or agreement"""
    contract_name: str = Field(..., description="Name or title of the contract")
    parties: str | None = Field(None, description="Contracting parties")
    effective_date: str | None = Field(None, description="Contract effective date")
    terms: str | None = Field(None, description="Key contract terms")
    governing_law: str | None = Field(None, description="Governing law clause")
    dispute_resolution: str | None = Field(None, description="Dispute resolution mechanism")


# Dictionary mapping entity type names to their Pydantic models
LEGAL_ENTITY_TYPES = {
    "Judge": Judge,
    "Attorney": Attorney,
    "Court": Court,
    "LegalCase": LegalCase,
    "Statute": Statute,
    "LegalPrecedent": LegalPrecedent,
    "LegalDocument": LegalDocument,
    "LegalEntity": LegalEntity,
    "LegalProcedure": LegalProcedure,
    "Expert": Expert,
    "Evidence": Evidence,
    "Claim": Claim,
    "Contract": Contract,
}

# Commonly used entity type subsets for different legal contexts
LITIGATION_ENTITIES = {
    "Judge": Judge,
    "Attorney": Attorney,
    "Court": Court,
    "LegalCase": LegalCase,
    "Expert": Expert,
    "Evidence": Evidence,
    "Claim": Claim,
}

RESEARCH_ENTITIES = {
    "LegalPrecedent": LegalPrecedent,
    "Statute": Statute,
    "Court": Court,
    "Judge": Judge,
}

CONTRACT_ENTITIES = {
    "Contract": Contract,
    "LegalEntity": LegalEntity,
    "Attorney": Attorney,
}
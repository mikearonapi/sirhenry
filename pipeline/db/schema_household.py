"""Backward-compatible re-exports. All models now live in schema.py."""
from .schema import (  # noqa: F401
    Base,
    HouseholdProfile,
    BenefitPackage,
    HouseholdOptimization,
    TaxProjection,
    LifeEvent,
    InsurancePolicy,
    FamilyMember,
    BenchmarkSnapshot,
)

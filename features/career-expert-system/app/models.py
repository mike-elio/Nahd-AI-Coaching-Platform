"""Pydantic models and fact-schema definitions for the GPES app."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


# Enums

class DomainEnum(str, Enum):
    SE = "SE"
    AIE = "AIE"
    CNE = "CNE"


class QuestionTypeEnum(str, Enum):
    BOOLEAN = "boolean"
    SCALE = "scale"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"
    NUMERIC = "numeric"


class LevelEnum(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


# Sub-models

class PoolItem(BaseModel):
    """One question variant inside a pool_pair."""

    id: str = Field(..., description="Unique ID for this variant, e.g. N_SE_001a")
    text_ar: str = Field(..., min_length=1, description="Question text in Arabic")
    text_en: str = Field(..., min_length=1, description="Question text in English")


# Main Node model

class QuestionNode(BaseModel):
   

    id: str = Field(..., description="Unique node ID, e.g. N_SE_001")
    domain: DomainEnum
    pool_pair: list[PoolItem] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Exactly 2 question variants",
    )
    fact_key: str = Field(..., description="The fact this question populates")
    type: QuestionTypeEnum = Field(..., description="Question type")
    level_filter: list[LevelEnum] = Field(
        ...,
        min_length=1,
        description="Which levels see this question",
    )
    weight: int = Field(..., ge=0, description="Importance weight for scoring")
    next_if_true: str = Field(
        ...,
        description="Node ID to go to on truthy answer, or 'END'",
    )
    next_if_false: str = Field(
        ...,
        description="Node ID to go to on falsy answer, or 'END'",
    )
    source_citation: str = Field(
        ...,
        min_length=1,
        description="Academic or professional source reference",
    )

    # Optional fields (type-specific)
    scale_min: int | None = Field(None, description="Min value for scale questions")
    scale_max: int | None = Field(None, description="Max value for scale questions")
    numeric_min: int | float | None = Field(None, description="Min value for numeric questions")
    numeric_max: int | float | None = Field(None, description="Max value for numeric questions")
    truthy_rule: str | None = Field(
        None,
        description="Rule for truthy evaluation, e.g. '>= 8'",
    )
    choices_ar: list[str] | None = Field(
        None,
        description="Arabic choice labels for choice or multi_choice questions",
    )
    choices_en: list[str] | None = Field(
        None,
        description="English choice labels for choice or multi_choice questions",
    )

    # Validators
    @field_validator("source_citation")
    @classmethod
    def citation_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_citation must not be blank")
        return v

    @field_validator("choices_ar", "choices_en")
    @classmethod
    def choices_not_blank(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        if not values:
            raise ValueError("choices lists must not be empty when provided")
        for value in values:
            if not value or not value.strip():
                raise ValueError("choice labels must not be blank")
        return values


UNIVERSAL_FACTS: dict[str, str] = {
    "user_type": "enum: student | graduate",
    "current_level": "enum: beginner | intermediate | advanced",
    "hours_per_week": "integer (1..40)",
    "target_outcome": "enum: internship | job | research | freelance",
    "time_horizon": "enum: short | medium | long",
    "weak_device": "boolean",
    "weak_internet": "boolean",
    "pressure_load": "enum: low | medium | high",
    "prefers_projects": "boolean",
    "english_level": "enum: basic | intermediate | advanced",
}

SE_FACTS: dict[str, str] = {
    "python_skill": "scale 0..5",
    "js_skill": "scale 0..5",
    "sql_skill": "scale 0..5",
    "problem_solving": "scale 0..5",
    "prefers_backend": "boolean",
    "prefers_frontend": "boolean",
    "prefers_devops": "boolean",
    "prefers_security": "boolean",
    "linux_skill": "scale 0..5",
    "math_tolerance": "boolean",
    "programming_basic": "boolean",
    "basics_control_flow": "boolean",
    "pretrack_readiness": "scale 0..5",
    "prefers_building_apps": "boolean",
    "api_concepts": "boolean",
    "status_codes_basic": "boolean",
    "api_documentation_openapi": "boolean",
    "db_modeling_skill": "scale 0..5",
    "input_validation": "boolean",
    "backend_testing": "boolean",
    "http_caching": "boolean",
    "config_12factor": "boolean",
    "indexes_query_perf": "boolean",
    "transactions_acid": "boolean",
    "isolation_levels": "boolean",
    "data_modeling_erd": "boolean",
    "data_quality_thinking": "boolean",
    "data_pipeline_basics": "boolean",
    "version_control_git": "boolean",
    "commit_conventions": "boolean",
    "ci_basics": "boolean",
    "cd_understanding": "boolean",
    "containers_basics": "boolean",
    "kubernetes_basics": "boolean",
    "observability_sre": "boolean",
    "config_management": "boolean",
    "threat_modeling_basic": "boolean",
    "authz_access_control": "boolean",
    "secure_coding_input": "boolean",
    "dependency_security": "boolean",
    "secure_sdcl_practices": "boolean",
    "supply_chain_security": "boolean",
    "web_basics": "scale 0..5",
    "dom_events": "boolean",
    "frontend_state_management": "boolean",
    "http_client_basics": "boolean",
    "cors_understanding": "boolean",
    "ui_accessibility": "boolean",
    "frontend_testing": "boolean",
    "ui_performance": "boolean",
    "normalization_basic": "boolean",
    "prefers_data": "boolean",
    "data_pipeline_concepts": "boolean",
    "data_quality_awareness": "boolean",
    "etl_tools_experience": "boolean",
    "data_visualization": "boolean",
    "big_data_basics": "boolean",
    "data_governance_awareness": "boolean",
    "cicd_basic": "boolean",
    "container_basics": "boolean",
    "iac_concepts": "boolean",
    "monitoring_basics": "boolean",
    "cloud_basics": "boolean",
    "sre_principles": "boolean",
    "gitops_concepts": "boolean",
    "devops_security_awareness": "boolean",
    "security_mindset": "boolean",
    "owasp_awareness": "boolean",
    "auth_concepts": "boolean",
    "encryption_basics": "boolean",
    "secure_coding": "boolean",
    "vulnerability_scanning": "boolean",
    "incident_response_basics": "boolean",
    "security_compliance_awareness": "boolean",
}

AIE_FACTS: dict[str, str] = {
    "python_skill": "scale 0..5",
    "math_skill": "scale 0..5",
    "ml_exposure": "scale 0..5",
    "data_handling": "scale 0..5",
    "prefers_ml": "boolean",
    "prefers_cv": "boolean",
    "prefers_nlp": "boolean",
    "prefers_data_eng": "boolean",
    "research_interest": "boolean",
    "pretrack_readiness": "scale 0..5",
    "python_skill_basic": "boolean",
    "any_programming_experience": "boolean",
    "ml_awareness": "boolean",
    "paper_reading_habit": "boolean",
    "experiment_design_skill": "boolean",
    "reinforcement_learning_interest": "boolean",
    "linear_algebra_skill": "scale 0..5",
    "image_processing_basics": "boolean",
    "cnn_understanding": "scale 0..5",
    "augmentation_overfitting": "boolean",
    "cv_task_preference": "enum: classification | detection | segmentation | tracking | not sure",
    "cv_deployment_interest": "boolean",
    "nlp_preprocessing": "boolean",
    "transformer_understanding": "scale 0..5",
    "nlp_evaluation_skill": "boolean",
    "nlp_track_preference": "enum: classical NLP | transformers from scratch | fine-tuning | RAG/retrieval | not sure",
    "data_privacy_ethics_awareness": "boolean",
    "nlp_project_experience": "boolean",
    "sql_skill": "scale 0..5",
    "etl_pipeline_experience": "boolean",
    "data_quality_monitoring": "boolean",
    "versioning_lineage": "boolean",
    "cloud_data_tools_exposure": "enum: Azure | AWS | GCP | None",
    "ml_systems_awareness": "boolean",
    "classical_models_understanding": "boolean",
    "model_evaluation_skill": "boolean",
    "feature_engineering_leakage": "boolean",
    "deep_learning_interest": "boolean",
    "deployment_interest": "boolean",
}

CNE_FACTS: dict[str, str] = {
    "networking_theory": "scale 0..5",
    "cisco_tools": "scale 0..5",
    "linux_skill": "scale 0..5",
    "scripting_skill": "scale 0..5",
    "prefers_netsec": "boolean",
    "prefers_wireless": "boolean",
    "prefers_cloud_net": "boolean",
    "prefers_iot": "boolean",
    "lab_access": "boolean",
    "networking_basic": "boolean",
    "osi_layers_basic": "boolean",
    "ip_subnetting_basic": "boolean",
    "tcp_udp_basic": "boolean",
    "basic_troubleshooting_tools": "boolean",
    "cne_focus_area": "enum: routing_switching | transport_web | wireless_wifi | network_security | cloud_datacenter | telecom_5g | not_sure",
    "linux_cli_net_tools_skill": "scale 0..5",
    "routing_models_understanding": "boolean",
    "routing_algorithms_basic": "boolean",
    "ospf_basic": "boolean",
    "bgp_basic": "boolean",
    "vlan_8021q_basic": "boolean",
    "stp_loop_prevention": "boolean",
    "arp_basic": "boolean",
    "dhcp_dora_basic": "boolean",
    "nat_pat_basic": "boolean",
    "tcp_state_machine_basic": "boolean",
    "reliability_mechanisms_basic": "boolean",
    "congestion_control_basic": "boolean",
    "rto_rtt_basic": "boolean",
    "http_semantics_stateless": "boolean",
    "http2_multiplexing_basic": "boolean",
    "quic_http3_basic": "boolean",
    "dns_resolution_basic": "boolean",
    "udp_app_guidelines_basic": "boolean",
    "wifi_80211_basic": "boolean",
    "wpa3_basic": "boolean",
    "wifi6_80211ax_basic": "boolean",
    "wireless_controller_capwap": "boolean",
    "rf_planning_skill": "scale 0..5",
    "enterprise_auth_8021x_eap": "boolean",
    "tls13_basic": "boolean",
    "pki_cert_validation": "boolean",
    "firewall_policy_basic": "boolean",
    "ipsec_basic": "boolean",
    "security_preference": "enum: tls_web | vpn_ipsec | firewalls_segmentation | enterprise_auth | pcap_ids | not_sure",
    "threat_modeling_skill": "scale 0..5",
    "cloud_familiarity": "enum: public | private | hybrid | multi | none | not_sure",
    "overlay_underlay_vxlan": "boolean",
    "sdn_openflow_basic": "boolean",
    "k8s_network_model_basic": "boolean",
    "cloud_routing_security_skill": "scale 0..5",
    "k8s_network_policy_basic": "boolean",
    "fiveg_core_components": "boolean",
    "network_slicing_basic": "boolean",
    "sip_voip_basic": "boolean",
    "rtp_rtcp_basic": "boolean",
    "qos_diffserv_basic": "boolean",
    "telecom_preference": "enum: core | ran | ims_voip | iot_cellular | ops_troubleshooting | not_sure",
}


def get_all_valid_fact_keys(domain: str | None = None) -> set[str]:
    keys = set(UNIVERSAL_FACTS)
    domain_map = {"SE": SE_FACTS, "AIE": AIE_FACTS, "CNE": CNE_FACTS}
    if domain and domain in domain_map:
        keys |= set(domain_map[domain])
        return keys
    for facts in domain_map.values():
        keys |= set(facts)
    return keys

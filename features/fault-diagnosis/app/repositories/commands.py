COMMAND_CATALOG = {
    "software": {
        "auth_artifact_integrity": [
            {
                "label": "Inspect the received Authorization header",
                "command": "curl -vk -H \"Authorization: Bearer <token>\" <service-url>/<route>",
                "purpose": "Replay the failing request with the exact identity artifact and inspect what reaches the service boundary.",
            }
        ],
        "auth_claim_validation": [
            {
                "label": "Decode JWT claims locally",
                "command": "python -m jwt.cli <token>",
                "purpose": "Check issuer, audience, expiry, subject, roles, and scopes before testing backend policy logic.",
            }
        ],
        "authorization_policy_check": [
            {
                "label": "Replay the protected operation with a known identity",
                "command": "curl -vk -H \"Authorization: Bearer <token>\" -X <method> <service-url>/<protected-route>",
                "purpose": "Confirm whether the route rejects a valid identity because of role, scope, or permission mapping.",
            }
        ],
        "session_cookie_boundary": [
            {
                "label": "Replay request with captured cookies",
                "command": "curl -vk -b cookies.txt -c cookies.txt <service-url>/<route>",
                "purpose": "Verify whether cookie scope, CSRF state, or credential continuity changes on the failing path.",
            }
        ],
        "replay_preflight_origin": [
            {
                "label": "Replay CORS preflight",
                "command": "curl -i -X OPTIONS <url> -H \"Origin: <origin>\" -H \"Access-Control-Request-Method: <method>\" -H \"Access-Control-Request-Headers: authorization\"",
                "purpose": "Compare the returned allow-origin, allow-method, allow-headers, and credential headers with the browser failure.",
            }
        ],
        "cors_origin_alignment": [
            {
                "label": "Check CORS response headers",
                "command": "curl -i <service-url>/<route> -H \"Origin: <origin>\"",
                "purpose": "Verify the actual edge/backend response headers for the failing origin.",
            }
        ],
        "react_request_construction": [
            {
                "label": "Inspect browser request shape",
                "command": "Open DevTools Network, preserve logs, replay the failing action, and inspect method, URL, headers, cookies, and payload.",
                "purpose": "Confirm the frontend sends the request shape the backend policy expects.",
            }
        ],
        "fastapi_dependency_path": [
            {
                "label": "Run the route dependency path under debug logging",
                "command": "uvicorn app.main:app --log-level debug",
                "purpose": "Confirm which FastAPI dependency or middleware branch rejects the failing request.",
            }
        ],
        "database_target_runtime_config": [
            {
                "label": "Print the live database target safely",
                "command": "python -c \"import os; print(os.getenv('DATABASE_URL', '<missing>').split('@')[-1])\"",
                "purpose": "Check the active host, database name, and port without exposing credentials.",
            }
        ],
        "database_runtime_reachability": [
            {
                "label": "Resolve database host",
                "command": "nslookup <db-host>",
                "purpose": "Confirm the configured database hostname resolves from the failing runtime context.",
            },
            {
                "label": "Test database TCP reachability",
                "command": "nc -vz <db-host> <port>",
                "purpose": "Confirm the failing runtime can open a socket to the configured database target.",
            },
            {
                "label": "Run a minimal PostgreSQL probe",
                "command": "psql \"<dsn>\" -c \"select 1;\"",
                "purpose": "Verify DNS, TCP reachability, authentication, and a minimal SQL round trip together.",
            }
        ],
        "postgresql_schema_state": [
            {
                "label": "Check PostgreSQL relation visibility",
                "command": "psql \"$DATABASE_URL\" -c \"select current_schema(), current_database(); \\dt\"",
                "purpose": "Verify the live schema and migration state used by the failing query.",
            }
        ],
        "mysql_target_contract": [
            {
                "label": "Check MySQL database and table contract",
                "command": "mysql \"$DATABASE_URL\" -e \"select database(); show tables;\"",
                "purpose": "Verify the runtime database and visible table contract.",
            }
        ],
    },
    "networking": {
        "runtime_dns_resolution": [
            {
                "label": "Resolve from the failing pod",
                "command": "kubectl exec -it <pod> -- nslookup <hostname>",
                "purpose": "Confirm service discovery from the same runtime context that experiences the failure.",
                "requires_any_tag": ["kubernetes"],
            },
            {
                "label": "Inspect service and endpoint registration",
                "command": "kubectl get svc,endpoints -n <namespace>",
                "purpose": "Verify that the service name resolves to registered live endpoints.",
                "requires_any_tag": ["kubernetes"],
            },
            {
                "label": "Check CoreDNS logs",
                "command": "kubectl logs -n kube-system deploy/coredns",
                "purpose": "Look for resolver errors, search path issues, or upstream DNS failures.",
                "requires_any_tag": ["kubernetes"],
            },
            {
                "label": "Check DNS resolution from the failing caller context",
                "command": "nslookup <hostname>",
                "purpose": "Confirm whether the failing caller can resolve the expected DNS hostname.",
            },
            {
                "label": "Compare DNS resolver answers",
                "command": "dig <hostname> A +short && dig @<resolver-ip> <hostname> A +short",
                "purpose": "Detect stale, split-horizon, or resolver-specific answer differences.",
            }
        ],
        "dns_answer_validation": [
            {
                "label": "Compare authoritative and runtime DNS answers",
                "command": "dig <service-name> A +short && dig @<resolver-ip> <service-name> A +short",
                "purpose": "Detect stale, split-horizon, or resolver-specific answer differences.",
            }
        ],
        "tls_chain_validation": [
            {
                "label": "Inspect TLS certificate and SNI behavior",
                "command": "openssl s_client -connect <host>:443 -servername <host> -showcerts",
                "purpose": "Confirm certificate chain, hostname coverage, SNI routing, and trust material.",
            }
        ],
        "transport_hop_validation": [
            {
                "label": "Trace the failing transport path",
                "command": "traceroute <host>",
                "purpose": "Check whether the route reaches the expected network boundary before failing.",
            }
        ],
        "upstream_route_validation": [
            {
                "label": "Replay through the edge with verbose transport output",
                "command": "curl -vk --resolve <host>:443:<edge-ip> https://<host>/<path>",
                "purpose": "Verify host preservation, route rewrite, and selected upstream at the edge.",
            }
        ],
        "proxy_forwarding_alignment": [
            {
                "label": "Inspect active proxy configuration",
                "command": "nginx -T | sed -n '/server_name <host>/,/}/p'",
                "purpose": "Confirm forwarded headers, upstream target, timeout, and rewrite directives.",
            }
        ],
        "kubernetes_service_mapping": [
            {
                "label": "Inspect Kubernetes service endpoints",
                "command": "kubectl get svc,endpoints,ingress -n <namespace> -o wide",
                "purpose": "Verify service selectors, endpoint registration, and ingress mapping for the failing path.",
            }
        ],
        "replay_preflight_origin": [
            {
                "label": "Replay CORS preflight",
                "command": "curl -i -X OPTIONS <url> -H \"Origin: <origin>\" -H \"Access-Control-Request-Method: <method>\" -H \"Access-Control-Request-Headers: authorization\"",
                "purpose": "Compare the edge and backend CORS policy returned to the failing origin.",
            }
        ],
    },
    "ai": {
        "serving_endpoint_mode": [
            {
                "label": "Query serving endpoint metadata",
                "command": "curl -s <model-server-url>/v1/models",
                "purpose": "Confirm the failing request reaches the intended model endpoint, branch, and runtime mode.",
            }
        ],
        "model_runtime_validation": [
            {
                "label": "Check model runtime assets",
                "command": "python -c \"from pathlib import Path; print(sorted(p.name for p in Path('<model-dir>').iterdir())[:20])\"",
                "purpose": "Verify weights, tokenizer files, and mounted artifacts exist on the live serving target.",
            }
        ],
        "retrieval_vector_alignment": [
            {
                "label": "Compare embedding dimensions",
                "command": "python -c \"print('query_dim=', len(<query_embedding>)); print('index_dim=', <index_dimension>)\"",
                "purpose": "Confirm query embedding shape matches the active vector index contract.",
            }
        ],
        "rag_retrieval_path": [
            {
                "label": "Log retrieved document ids for one failing query",
                "command": "python -c \"print(<retriever>.invoke('<failing-query>'))\"",
                "purpose": "Verify the failing query hits the expected collection, namespace, filters, and documents.",
            }
        ],
        "tensor_shape_capture": [
            {
                "label": "Print tensor shape before model execution",
                "command": "print input tensor shape before model.forward",
                "purpose": "Capture the exact tensor contract entering the failing model layer.",
            },
            {
                "label": "Print first layer weight shape",
                "command": "print first layer weight shape",
                "purpose": "Compare the model's expected feature dimension against the incoming tensor.",
            },
            {
                "label": "Assert expected feature dimension",
                "command": "assert expected feature dimension",
                "purpose": "Fail fast at the preprocessing boundary instead of deeper in model.forward().",
            }
        ],
        "tensor_conversion_validation": [
            {
                "label": "Compare NumPy and PyTorch tensor metadata",
                "command": "python -c \"print(array.shape, array.dtype); print(tensor.shape, tensor.dtype, tensor.device)\"",
                "purpose": "Confirm dtype, layout, and dimension order survive conversion.",
            }
        ],
        "gpu_runtime_pressure": [
            {
                "label": "Inspect GPU memory pressure",
                "command": "nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv",
                "purpose": "Measure live GPU memory headroom and utilization during the failing workload.",
            }
        ],
        "cuda_capacity_check": [
            {
                "label": "Check CUDA availability from the runtime",
                "command": "python -c \"import torch; print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')\"",
                "purpose": "Confirm CUDA, driver-visible GPU, and framework runtime alignment.",
            }
        ],
        "gpu_utilization_check": [
            {
                "label": "Watch GPU queue and memory during replay",
                "command": "nvidia-smi dmon -s pucm",
                "purpose": "Observe whether the failure correlates with utilization, memory, or fallback behavior.",
            }
        ],
    },
}

GENERIC_COMMANDS = {
    "software": [
        {
            "label": "Replay the failing request with verbose output",
            "command": "curl -vk <service-url>/<route>",
            "purpose": "Capture status, headers, redirects, and transport details for one reproducible failure.",
        }
    ],
    "networking": [
        {
            "label": "Check endpoint reachability",
            "command": "curl -vk <url>",
            "purpose": "Confirm whether the failure occurs before or after the HTTP/TLS boundary.",
        }
    ],
    "ai": [
        {
            "label": "Run one minimal inference replay",
            "command": "python -c \"print(model(**inputs))\"",
            "purpose": "Reproduce the failure with the smallest workload that still exercises the same model path.",
        }
    ],
}


__all__ = ["COMMAND_CATALOG", "GENERIC_COMMANDS"]

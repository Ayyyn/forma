# Upstream Dockerfiles leave ocp_gordon unpinned. Version 0.3.1 imports
# OCP.collections, absent from their required cadquery-ocp 7.8.1.1.post1.
# Pin the same compatible version as the previous Windows evaluator.
ARG BASE
FROM ${BASE}
RUN uv pip install --system --no-deps ocp_gordon==0.1.17

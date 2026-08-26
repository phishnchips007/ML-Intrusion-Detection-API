# ML Intrusion Detection API

This repository contains a portfolio proof-of-concept FastAPI service for the
stored Random Forest inference model. The service preserves the model artifact,
its stored 74-feature contract, and the existing `/health` and `/predict`
responses.

## Container security review disposition

The Milestone 2 container uses the current pinned Python 3.11.16 slim Trixie
multi-platform image, removes `pip`, `setuptools`, and `wheel` after runtime
dependency installation, and runs the API as an unprivileged user. The CI
smoke check exercises the real health and inference endpoints with the local
runtime restrictions documented in `scripts/container_smoke.sh`.

This is portfolio-scale baseline security proof, not a production release. The
security rescan still reports two critical and six high findings in the base
image. The two critical Perl findings and two additional Perl highs have no
reported Debian fix and are accepted because the API does not invoke Perl or
expose Perl-controlled paths. Four OpenSSL highs remain accepted until an
official Python base refresh includes the reported fixed Debian package; the
service does not shell out to the OpenSSL CLI. These are tracked residual base
image limitations rather than claims that the image is vulnerability-free.

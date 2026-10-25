# Project 1 — container delivery

Use the coordinated infrastructure repository for the complete architecture, bootstrap, variable matrix, deployment steps and recovery guide:

https://github.com/rajmohanb82/aws-autoapp-infra-repo

This repo owns `.github/workflows/application.yml`, `scripts/deploy.py`, `scripts/deploy-host.sh`, tests and the hardened portal image. Dev builds and deploys on push. Production runs manually from `production`, promotes the digest currently deployed to dev and requires a configured GitHub environment approval.

Database and Python bytecode files previously tracked by git are removed from the working tree in this change. They remain in historical commits: inspect the old database for any live secrets and rotate those before using this as a public portfolio. No history rewrite was performed.

The existing docker-compose.yml remains a local-development entry point; the AWS path uses SSM and ECR without mounting local AWS profiles.

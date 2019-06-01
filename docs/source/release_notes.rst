Release Notes
================================================================

Release 1.1: Known Issues
--------------------------------------

* For merge workspace, the new pod is mounting two volumes, one volume with the source workspace and the other volume with a copy of the selected build. The changes have to be merged manually by the developer
* The UID and GID for the workspace and service volumes are defaulted to 0, 0. We will provide customizable UID, GID values in 1.2
* Manual webhook setup for GitLab and Jenkins integration is required for every pipeline
* The solution is only tested with ONTAP using NFS volumes
* The CI pipeline build clones are required to be purged manually
* The number of active clones (build and workspace) is limited by ONTAP. Please check the ONTAP release and make sure the purge policies are in place
* In case of failure during pipeline or workspace creation, the Kubernetes PVCs may have to be purged manually
* For GitLab, the URL for git cloning is incorrect. Please use http://<$SERVICE_URL>:<devops-at-scale-gitlab-port>/ during git clone.

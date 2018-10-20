Sample CI pipeline for Build-At-Scale
==========================================

   .. code :: shell

			  def generateTimeStamp() {
			  def now = new Date()
				return now.format("yyyyMMddmmss", TimeZone.getTimeZone('UTC'))
			   }

			  def replaceDashesAndPeriods(oldString) {
				def newString = oldString
				newString = newString.replaceAll('[.|-]','_')
				return newString
			  }

			  // Global Variables

			  def jobName = "${JOB_NAME}"
			  def jobNameNoUnderScores = jobName.replaceAll('_','-')
			  def pvcName =  "${jobNameNoUnderScores}-pvc"
			  def volumeMountPath = '/mnt/' + params.BUILDVOL
			  def podName =  "${jobNameNoUnderScores}-${BUILD_NUMBER}-pod"
			  def podLabel = "${jobNameNoUnderScores}-${BUILD_NUMBER}-pod"
			  def gitDir = volumeMountPath + '/git'
			  def buildDir = gitDir
			  def sourceCodeURL = params.SOURCE_CODE_URL
			  def sourceCodeBranch = params.SOURCE_CODE_BRANCH
			  def gitVolume = params.GIT_VOLUME
			  def broker_url = params.BROKER_URL
			  def scmSnapshotName = ""
			  def ciSnapshotName = ""
			  def currentGitRevision = ""
			  def build_status = "passed"

			  echo "Running CI Pipeline"
			  echo "Note: This Pipeline expects that a pvc with name ${pvcName} is available prior to running"

			  // Define Kubernetes Pod that we will use for this job and mount Ontap Volume on this POD
			  // We need to mount /var/run/docker.sock for DIND builds (Docker in Docker)
			  podTemplate(name: podName , label: podLabel,
			  volumes: [hostPathVolume(hostPath: '/var/run/docker.sock', mountPath: '/var/run/docker.sock'),
						persistentVolumeClaim(claimName: pvcName, mountPath: volumeMountPath, readOnly: false)],
			  containers: [
				  containerTemplate(
					  name: 'jnlp',
					  workingDir: '/home/jenkins_slave_workspace',
					  image: "${params.JENKINS_SLAVE_IMAGE}",
					  args: '${computer.jnlpmac} ${computer.name}',
					  alwaysPullImage: true,
				  ), ]

			  )
			  {
				node('master')
				{
					  stage('Create SCM snapshot')
					  {
						def scmTrigger = currentBuild.rawBuild.getAction(hudson.plugins.git.RevisionParameterAction)
						if (scmTrigger) {
						  currentGitRevision = scmTrigger.commit
						  gitRevShorthand = currentGitRevision.take(7)
						  scmSnapshotName = gitRevShorthand + '_' + generateTimeStamp()
						  sh "curl -X POST ${broker_url}/backend/snapshot/create -F volume_name=${params.GIT_VOLUME} -F jenkins_build=${BUILD_NUMBER} -F 'snapshot_name=${scmSnapshotName}' -F 'type=scm' "
						  echo "SCM snapshot created: ${scmSnapshotName}"
						}
						else {
						  echo "Build not triggered by scm hook , skipping SCM snapshot creation"
						}
					  }
				}

			  // Run Main CI Process on Pod
				  node(podLabel)
				  {
					  stage('Setup') {
						  sh "mkdir -p ${gitDir}"
						  echo 'Check if netapp volume is correctly mounted'
						  if (! fileExists(gitDir)) {
							  error "could not find ${gitDir}, check ONTAP volume is mounted!"
						  }

					  }
					  stage('Checkout') {
						  if (params.RUN_CLEAN_BUILD) {
							  echo "Running Clean Build"
							  sh "sudo rm -rf ${volumeMountPath}/*"
						  }

						  dir (gitDir) {
							   sh 'git config --global http.sslVerify false'
							   checkout([$class: 'GitSCM',
								   branches: [[name: "*/${sourceCodeBranch}"]],
					   doGenerateSubmoduleConfigurations: false,
					   extensions: [[$class: "LocalBranch", localBranch: '**']],
					   submoduleCfg: [],
					   userRemoteConfigs: [[
						url: "${sourceCodeURL}"
					   ]]])
							  currentGitRevision = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
							  if (currentBuild.description)
								  currentBuild.description  = currentBuild.description + "\n"
							  else
								  currentBuild.description = ""
							  currentBuild.description = currentBuild.description + "Commit: " + currentGitRevision.take(7)
						  }
					  }
					  stage('Build') {
						  try {
							sh "mkdir -p ${buildDir} || true"
							dir(buildDir) {
								// Build commands should go here
								echo 'running build'
							}
						  }
						  catch(Exception e) {
							build_status = 'failed'
							println("Build Error: ${e.message}")
						  }
						  }

						  stage('Deploy To Apprenda') {

							 build job: 'Deploy_To_Apprenda', parameters: [[$class: 'LabelParameterValue', name: 'node', label: "${podLabel}"]]

						   }

					 }




				  }




			  // Create Snapshot and add to Snapshot List
			  // This should all be done on master

				  node('master') {

					  stage('Create CI Snapshot') {
						gitRevShorthand = currentGitRevision.take(7)
						ciSnapshotName = gitRevShorthand + '_' + BUILD_NUMBER + '_' + generateTimeStamp()
						sh "curl -X POST ${broker_url}/backend/snapshot/create -F volume_name=${params.BUILDVOL} -F jenkins_build=${BUILD_NUMBER} -F 'snapshot_name=${ciSnapshotName}' -F 'build_status=${build_status}' -F 'type=ci'"
						echo "CI snapshot created: ${ciSnapshotName}"
					  }
					  stage('Determine overall build status') {
						if (build_status == 'failed') {
							sh "exit 1"
						}
					  }
				  }

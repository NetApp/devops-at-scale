pipeline {
  triggers {
    pollSCM('* * * * *')
  }
  agent {
    label 'hub'
  }
  options {
    disableConcurrentBuilds()
  }
  stages {
    stage('Set up Environment') {
      steps {
        sh "echo ${env.BRANCH_NAME} > sonar-branch"
        sh "cat sonar-branch | cut -d'/' -f 2- > sonar-branch2"
        sh 'cat sonar-branch2'
        script {
          env.SONAR_NAME = readFile 'sonar-branch2'
        }
      }
    }
    stage('Static Analysis') {
      parallel {
        stage('Pep 8 Modules') {
          steps {
            sh "python3 /usr/bin/pycodestyle --max-line-length=160 --ignore=E305,E402,W503,W504,E722,E741 web_service/web_service"
          }
        }
        stage('Pylint') {
          steps {
            sh "python3 /usr/bin/pylint --ignore=ontap --max-line-length=160 --disable=R,C,W web_service/web_service"
          }
        }
        stage('Hub Scan') {
          steps {
            sh '''
              # export BD_HUB_TOKEN=<hub-token>
              # /tmp/scan.cli-2018.12.0/bin/scan.cli.sh --scheme https --port 443 --insecure --host blackduck.eng.netapp.com --project 'Build@Scale' --release '1.1' ./
              export BD_HUB_PASSWORD=<hub-password>
              /tmp/scan.cli-2018.12.0/bin/scan.cli.sh --scheme https --port 443 --insecure --host blackduck.eng.netapp.com --project 'Build@Scale' --release '1.1' --username=sysadmin ./
            '''
          }
        }
      }
    }
    stage('Unit Test') {
      parallel {
        stage('Backend') {
          steps {
            sh '''
              cd web_service &&
              pytest web_service/backend
            '''
          }
        }
        stage('Database') {
          steps {
            sh '''
              cd web_service
              pytest web_service/database
            '''
          }
        }
        stage('Jenkins') {
          steps {
            sh '''
              cd web_service
              pytest web_service/jenkins
            '''
          }
        }
        stage('Kubernetes') {
          steps {
            sh '''
              cd web_service
              pytest web_service/kub
            '''
          }
        }
        stage('Helpers') {
          steps {
            sh '''
              cd web_service
              pytest web_service/helpers
            '''
          }
        }
        stage('ONTAP') {
          steps {
            sh '''
              cd web_service
              pytest web_service/ontap
            '''
          }
        }
      }
    }
  }
  post {
    always {
      deleteDir() /* clean up our workspace */
    }
  }
}

pipeline {
  agent any

  environment {
    PROJECT_ID = 'ai-sre-platform-506305'
    REGION     = 'us-central1'
    REPO       = "us-central1-docker.pkg.dev/${PROJECT_ID}/ai-sre-images"
    CLUSTER    = 'ai-sre-cluster'
  }

  stages {                                    // <-- ADDED: opens the stages block

    stage('Authenticate to GCP') {
      steps {
        sh '''
          gcloud config set project $PROJECT_ID
          gcloud auth configure-docker $REGION-docker.pkg.dev --quiet
          gcloud container clusters get-credentials $CLUSTER --region $REGION
        '''
      }
    }

    stage('Build & Push Images') {
      steps {
        sh '''
          docker build -t $REPO/backend:${BUILD_NUMBER} ./backend
          docker push $REPO/backend:${BUILD_NUMBER}

          docker build -t $REPO/frontend:${BUILD_NUMBER} ./frontend
          docker push $REPO/frontend:${BUILD_NUMBER}
        '''
      }
    }

    stage('Deploy to GKE') {
      steps {
        sh '''
          kubectl set image deployment/backend backend=$REPO/backend:${BUILD_NUMBER}
          kubectl set image deployment/frontend frontend=$REPO/frontend:${BUILD_NUMBER}
          kubectl set image deployment/agent-watcher watcher=$REPO/backend:${BUILD_NUMBER}
          kubectl rollout status deployment/backend
          kubectl rollout status deployment/frontend
          kubectl rollout status deployment/agent-watcher
        '''
      }
    }

  }                                           // <-- ADDED: closes the stages block

  post {
    success { echo "✅ Deployed build ${BUILD_NUMBER} successfully!" }
    failure { echo "❌ Build ${BUILD_NUMBER} failed." }
  }
}


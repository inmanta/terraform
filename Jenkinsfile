pipeline {
    agent any
    triggers {
        cron(BRANCH_NAME == 'master' ? 'H H(2-5) * * *' : '')
    }
    options {
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 120, unit: 'MINUTES')
    }
    stages {
        stage('setup') {
            steps {
                script {
                    sh '''
                    python3 -m venv ${WORKSPACE}/env
                    . ${WORKSPACE}/env/activate
                    make install
                    '''
                }
            }
        }
        stage('code linting') {
            steps {
                script {
                    sh'''
                    . ${WORKSPACE}/env/activate
                    make pep8
                    '''
                }
            }
        }
        stage('tests') {
            steps {
                script {
                    withCredentials([
                        // For Checkpoint provider tests
                        usernamePassword(
                            credentialsId: 'checkpoint_credentials',
                            usernameVariable: 'CHECKPOINT_USER',
                            passwordVariable: 'CHECKPOINT_PASS'
                        ),
                        // For Fortios provider tests
                        string(
                            credentialsId: 'fortios_token', 
                            variable: 'FORTIOS_TOKEN'
                        ),
                        string(
                            credentialsId: 'fortios_switch_id', 
                            variable: 'FORTIOS_SWITCH_ID'
                        ),
                        // For GitHub provider tests
                        string(
                            credentialsId: 'jenkins_on_github',
                            variable: 'GITHUB_TOKEN'
                        ),
                        // For Gitlab provider tests
                        string(
                            credentialsId: 'jenkins_on_gitlab',
                            variable: 'GITLAB_TOKEN'
                        )
                    ]) {
                        sh'''
                        ${WORKSPACE}/env/bin/pytest tests \
                            --lab ci \
                            --log-cli-level=DEBUG \
                            -v -s \
                            --junitxml=junit.xml
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            deleteDir()
        }
    }
}

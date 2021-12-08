pipeline {
    agent any
    triggers {
        cron(BRANCH_NAME == 'master' ? 'H H(2-5) * * *' : '')
    }
    options {
        disableConcurrentBuilds()
        gitLabConnection('code.inmanta.com')
        timestamps()
        timeout(time: 120, unit: 'MINUTES')
    }
    stages {
        stage('setup') {
            steps {
                updateGitlabCommitStatus name: 'build', state: 'pending'
                script {
                    sh '''
                    python3 -m venv ${WORKSPACE}/env
                    "${WORKSPACE}"/env/bin/pip install -U pip ${PIP_OPTIONS}
                    "${WORKSPACE}"/env/bin/pip install -r requirements.txt --pre -i https://artifacts.internal.inmanta.com/inmanta/dev
                    "${WORKSPACE}"/env/bin/pip install -r requirements.dev.txt --pre -i https://artifacts.internal.inmanta.com/inmanta/dev
                    '''
                }
            }
        }
        stage('code linting') {
            steps {
                script {
                    sh'''
                    ${WORKSPACE}/env/bin/flake8 plugins tests
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
        failure {
            updateGitlabCommitStatus name: 'build', state: 'failed'
        }
        success {
            updateGitlabCommitStatus name: 'build', state: 'success'
        }
        always {
            deleteDir()
        }
    }
}

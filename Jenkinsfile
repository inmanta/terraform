pipeline {
    // Set agent to none to makes sure that Jenkins doesn't acquire a builder slot,
    // while waiting for a lock. The agent for the actual execution is set in the
    // stages section.
    agent none

    triggers {
        cron(BRANCH_NAME == 'master' ? 'H H(2-5) * * *' : '')
    }
    options {
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 120, unit: 'MINUTES')
        lock("terraform-module-ci-lab")
    }
    stages {
        stage("Main stage") {
            agent any
            stages {
                stage('setup') {
                    steps {
                        script {
                            sh '''
                            export PIP_INDEX_URL=https://artifacts.internal.inmanta.com/inmanta/dev
                            python3 -m venv ${WORKSPACE}/env
                            . ${WORKSPACE}/env/bin/activate
                            make install
                            '''
                        }
                    }
                }
                stage('code linting') {
                    steps {
                        script {
                            sh'''
                            . ${WORKSPACE}/env/bin/activate
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
                                    usernameVariable: 'TERRAFORM_CHECKPOINT_USER',
                                    passwordVariable: 'TERRAFORM_CHECKPOINT_PASS'
                                ),
                                // For Fortios provider tests
                                string(
                                    credentialsId: 'fortios_token',
                                    variable: 'TERRAFORM_FORTIOS_TOKEN'
                                ),
                                string(
                                    credentialsId: 'fortios_switch_id',
                                    variable: 'TERRAFORM_FORTIOS_SWITCH_ID'
                                ),
                                // For GitHub provider tests
                                string(
                                    credentialsId: 'jenkins_on_github',
                                    variable: 'TERRAFORM_GITHUB_TOKEN'
                                ),
                                // For Gitlab provider tests
                                string(
                                    credentialsId: 'jenkins_on_gitlab',
                                    variable: 'TERRAFORM_GITLAB_TOKEN'
                                )
                            ]) {
                                sh'''
                                export INMANTA_TERRAFORM_SKIP_PROVIDER_CHECKPOINT="true"
                                export INMANTA_TERRAFORM_SKIP_PROVIDER_FORTIOS="false"
                                export INMANTA_TERRAFORM_SKIP_PROVIDER_GITHUB="false"
                                export INMANTA_TERRAFORM_SKIP_PROVIDER_GITLAB="false"
                                export INMANTA_TERRAFORM_SKIP_PROVIDER_LOCAL="false"
                                ${WORKSPACE}/env/bin/pytest tests \
                                    --terraform-lab ci \
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
    }
}

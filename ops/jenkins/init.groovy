import jenkins.model.Jenkins
import hudson.plugins.git.GitSCM
import hudson.plugins.git.BranchSpec
import hudson.plugins.git.UserRemoteConfig
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition

// Local, single-user development only. Keep the setup wizard and login enabled.
def instance = Jenkins.get()
instance.setNumExecutors(1)
if (instance.getItem('pulsegrid') == null) {
    def scm = new GitSCM(
        [new UserRemoteConfig('file:///repo', null, null, null)],
        [new BranchSpec('*/codex/jenkins-pipeline')],
        false, [], null, null, [])
    def job = instance.createProject(WorkflowJob, 'pulsegrid')
    job.setDefinition(new CpsScmFlowDefinition(scm, 'Jenkinsfile'))
    job.save()
}
instance.save()

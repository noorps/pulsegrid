import jenkins.model.Jenkins
import hudson.plugins.git.GitSCM
import hudson.plugins.git.BranchSpec
import hudson.plugins.git.UserRemoteConfig
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition

def instance = Jenkins.get()
instance.setNumExecutors(1)
if (instance.getItem('pulsegrid') == null) {
    def scm = new GitSCM(
        [new UserRemoteConfig('file:///repo', null, null, null)],
        [new BranchSpec('*/' + (System.getenv('PULSEGRID_BRANCH') ?: 'main'))],
        false, [], null, null, [])
    def job = instance.createProject(WorkflowJob, 'pulsegrid')
    job.setDefinition(new CpsScmFlowDefinition(scm, 'Jenkinsfile'))
    job.save()
}
instance.save()

$(document).ready(function() {
  $.ajax({
      url: '/frontend/workspace/git-projects'
    })
    .done(function(data) {
      formatPipelineForm(data);
    });
  var projectSelect = document.getElementById('git-projects-select')
  var repoSelect = document.getElementById('git-repos-select')
  var branchSelect = document.getElementById('git-branches-select')
  var scmURL = document.getElementById('scm-url')

  function formatPipelineForm(data) {
    $.each(data['projects'], function(index, project) {
      var option = document.createElement("option");
      option.innerHTML = project['name'];
      option.value = project['name'];
      option.key = project['key'];
      // then append it to the select element
      projectSelect.appendChild(option);
    });
  }

  projectSelect.onchange = function() {
    // clear all existing selections, only when project changes
    document.getElementById('git-repos-select').value = ""
    document.getElementById('git-branches-select').value = ""
    document.getElementById('scm-branch').value = ""
    document.getElementById('scm-url').value = ""
    var projectKey = projectSelect.options[projectSelect.options.selectedIndex].key
    var url = "/frontend/workspace/git-repositories/" + projectKey
    $.ajax({
      url: url,
      success: function(data) {
        $.each(data['repos'], function(index, repo) {
          var option = document.createElement("option");
          option.innerHTML = repo['name'];
          option.value = repo['name'];
          // assign the http clone url as key
          if (repo['links']['clone'][0]['name'] == 'http')
            option.key = repo['links']['clone'][0]['href'];
          else
            option.key = repo['links']['clone'][1]['href'];
          repoSelect.appendChild(option)
        });
      }
    });
  }

  repoSelect.onchange = function() {
    var projectKey = projectSelect.options[projectSelect.options.selectedIndex].key
    var repoName = repoSelect.options[repoSelect.options.selectedIndex].value
    var url = "/frontend/workspace/git-branches/" + projectKey + "/" + repoName
    $.ajax({
      url: url,
      success: function(data) {
        $.each(data['branches'], function(index, branch) {
          var option = document.createElement("option");
          option.innerHTML = branch['displayId'];
          option.value = branch['displayId'];
          option.key = branch['displayId'];
          branchSelect.appendChild(option)
        });
      }
    });
  }

  branchSelect.onchange = function() {
    var scmBranch = document.getElementById('scm-branch')
    // scmBranch.innerHTML = branchSelect.options[branchSelect.options.selectedIndex].value
    scmBranch.value = branchSelect.options[branchSelect.options.selectedIndex].value
    scmURL.value = repoSelect.options[repoSelect.options.selectedIndex].key
  }
});

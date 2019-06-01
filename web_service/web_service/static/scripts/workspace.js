$(document).ready(function() {
  // When the page loads or the user hits back button, reset any form elements
  $(window).bind("pageshow", function() {
    $("#submit-button").button('reset');
  });

  var submitButton = document.getElementById('submit-button')
  submitButton.onclick = function() {
    var $this = $(this);
    $this.button('loading');
  }

  document.getElementById("workspace-create-tab").className = "active"
  $.ajax({
      url: '/frontend/workspace/pipelines'
    })
    .done(function(data) {
      formatWorkspaceForm(data);
    });
  var projectSelect = document.getElementById('git-projects-select')
  var buildSelect = document.getElementById('builds-select')
//  var volumeSelect = document.getElementById('volume-name')
  var pipelineName = document.getElementById('pipeline-name')
  var submitButton = document.getElementById('submit-button')

  function formatWorkspaceForm(data) {
    $.each(data['pipelines'], function(index, pipeline) {
      var option = document.createElement("option");
      option.innerHTML = pipeline;
      option.value = pipeline;
      // then append it to the select element
      projectSelect.appendChild(option);
    });
  }

  projectSelect.onchange = function() {
    document.getElementById('builds-select')
//    var volumeName = projectSelect.value.replace(/-|\./g, "_")
//    volumeSelect.value = volumeName
    pipelineName.value = projectSelect.value
    // pipelineName = pipelineName
    var url = "/backend/" + pipelineName.value + "/buildclones"
    $.ajax({
      url: url,
      success: function(data) {

        $.each(data, function(index, build) {
          var clone_name = build
          var option = document.createElement("option");
          option.innerHTML = clone_name;
          option.value = clone_name;
          buildSelect.appendChild(option)
        });
      }
    });
  }
  buildSelect.onchange = function() {
    var buildName = document.getElementById('build-name-with-status')
    buildName.value = buildSelect.value
  }

});

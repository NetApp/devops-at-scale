$(document).ready(function() {
  $.ajax({
      url: '/frontend/dashboard/pipelines'
    })
    .done(function(data) {
      formatDashboard(data);
    });

  function formatDashboard(data) {
    var i = 1;
    $.each(data['pipelines'], function(index, pipeline) {
      job_data = "<tr>" +
        "<td>" + i + "</td>" +
        "<td>" + pipeline['pipeline_name'] + "</td>" +
        "<td>" +
        "<a href=" + pipeline['scm_url'] + "> Bitbucket </a>" +
        "</td>" +
        "<td>" +
        "<a href=" + pipeline['jenkins_url'] + "> Jenkins </a>" +
        "</td>" +
        "<td>" + pipeline['last_build'] + "</td>" +
        "</tr>"
      i = i + 1
      $("#pipelines-body").append(job_data);
    });
  }
});

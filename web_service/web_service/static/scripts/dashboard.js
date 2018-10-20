function deleteWorkspace(me) {
  var workspace = $(me).val();
  $.post("/backend/workspace/delete", {
      "workspace-name": workspace
    },
    function(data) {
      window.location.replace("/frontend/dashboard");
    });
}
function deleteProject(me) {
  var project = $(me).val();
  $.post("/backend/project/delete", {
      "project-name": project
    },
    function(data) {
      window.location.replace("/frontend/dashboard");
    });
}

$(document).ready(function() {
  document.getElementById("dashboard-tab").className = "active"
});

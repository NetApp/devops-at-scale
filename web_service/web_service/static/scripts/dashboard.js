function deleteWorkspace(me) {
  var workspace = $(me).val();
  $.post("/backend/workspace/delete", {
      "workspace-name": workspace
    },
    function(data) {
      window.location.replace("/frontend/dashboard");
    });
}
function deletePipeline(me) {
  var pipeline = $(me).val();
  $.post("/backend/pipeline/delete", {
      "pipeline-name": pipeline
    },
    function(data) {
      window.location.replace("/frontend/dashboard");
    });
}

$(document).ready(function() {
  document.getElementById("dashboard-tab").className = "active"
});

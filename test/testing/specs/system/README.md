# Integration Tests

Tests components and component groups against one or more runtime service dependencies.

Differentiated from unit tests which may not have a runtime service dependency, 
and system tests, which may not have code dependencies.

In this case, there are both code dependencies and service dependencies.

Because it has code dependencies, it will contribute to coverage measurements.

Because it has service dependencies, it tends to be slow and requires those service 
dependencies to be running.



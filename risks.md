# Risk Register

## Critical Risks (Showstoppers)

### 1. API Rate Limiting / Blocking
**Probability**: Medium | **Impact**: High
- **Description**: yfinance or SEC blocks our requests
- **Detection Signals**:
  - HTTP 429 responses
  - Empty data returns
  - Connection timeouts increase
- **Mitigation**:
  - Implement exponential backoff
  - Add multiple data sources
  - Respect rate limits strictly
  - Cache aggressively
- **Recovery**: Switch to alternate data source, use cached data

### 2. Data Quality Issues
**Probability**: High | **Impact**: Medium
- **Description**: Missing, incorrect, or inconsistent data
- **Detection Signals**:
  - Validation failures >10%
  - Price gaps >5%
  - 13F parsing errors
- **Mitigation**:
  - Comprehensive validation
  - Multiple data sources
  - Clear data quality reporting
- **Recovery**: Flag issues in report, use alternate sources

### 3. LLM Hallucination
**Probability**: Medium | **Impact**: High
- **Description**: Ollama generates false information
- **Detection Signals**:
  - Numbers not in input data
  - Speculative language
  - Inconsistent facts
- **Mitigation**:
  - Strict prompt engineering
  - Output validation
  - Fact-checking against input
- **Recovery**: Fallback to template-only report

## High Priority Risks

### 4. Performance Degradation
**Probability**: Medium | **Impact**: Medium
- **Description**: Report generation takes >60 seconds
- **Detection Signals**:
  - SQLite queries >1 second
  - Memory usage >2GB
  - User complaints
- **Mitigation**:
  - Query optimization
  - Pagination
  - Caching layer
- **Recovery**: Add progress bars, optimize bottlenecks

### 5. Dependency Breaking Changes
**Probability**: Low | **Impact**: High
- **Description**: yfinance/pandas API changes
- **Detection Signals**:
  - Import errors
  - Method not found
  - Test failures
- **Mitigation**:
  - Pin versions
  - Abstraction layers
  - Regular updates
- **Recovery**: Rollback versions, update code

### 6. Disk Space Exhaustion
**Probability**: Low | **Impact**: Medium
- **Description**: Cache/data fills disk
- **Detection Signals**:
  - Write failures
  - Disk >80% full
  - Slow I/O
- **Mitigation**:
  - Rotation policies
  - Size monitoring
  - Cleanup routines
- **Recovery**: Clear cache, archive old data

## Medium Priority Risks

### 7. Scope Creep
**Probability**: High | **Impact**: Medium
- **Description**: Features added beyond MVP
- **Detection Signals**:
  - Unplanned work >20%
  - Delayed milestones
  - New dependencies
- **Mitigation**:
  - Strict plan.md adherence
  - Change control process
  - Regular reviews
- **Recovery**: Defer to backlog, reset to MVP

### 8. Security Vulnerability
**Probability**: Low | **Impact**: Medium
- **Description**: SQL injection, path traversal
- **Detection Signals**:
  - Unusual queries
  - File access outside data/
  - Error logs with paths
- **Mitigation**:
  - Input validation
  - Parameterized queries
  - Security scanning
- **Recovery**: Patch immediately, audit logs

### 9. Ollama Unavailability
**Probability**: Medium | **Impact**: Low
- **Description**: Ollama service not running
- **Detection Signals**:
  - Connection refused
  - Service not found
  - Timeout errors
- **Mitigation**:
  - Health checks
  - Auto-restart
  - Fallback templates
- **Recovery**: Start service, use template-only

## Low Priority Risks

### 10. Documentation Debt
**Probability**: High | **Impact**: Low
- **Description**: Docs out of sync with code
- **Detection Signals**:
  - User confusion
  - Wrong examples
  - Missing features
- **Mitigation**:
  - Doc updates in PR
  - Regular reviews
  - User feedback
- **Recovery**: Documentation sprint

## Risk Response Matrix

| Risk Level | Response Strategy | Review Frequency |
|------------|------------------|------------------|
| Critical | Prevent + Detailed Plan | Daily |
| High | Mitigate + Monitor | Weekly |
| Medium | Monitor + Plan | Bi-weekly |
| Low | Accept + Document | Monthly |

## Early Warning Dashboard

Monitor these metrics daily:
- API success rate <95% → Check risk #1
- Data validation failures >5% → Check risk #2
- Report generation >30s → Check risk #4
- Disk usage >60% → Check risk #6
- Unplanned tasks >3 → Check risk #7

## Escalation Path

1. **Detection**: Automated monitoring or user report
2. **Assessment**: Check impact and spread
3. **Response**: Execute mitigation plan
4. **Communication**: Update changelog.md
5. **Resolution**: Fix and document lessons
6. **Prevention**: Update risks.md and monitoring

## Risk Review Schedule

- **Daily**: Check critical risk indicators
- **Weekly**: Review high priority risks
- **Sprint End**: Full risk assessment
- **Monthly**: Update probability/impact ratings

## Contingency Time

- Add 20% buffer to all estimates
- Keep 1 day per week for risk response
- Plan for 1 major issue per sprint

# Identity and access: who a person is, how they stay signed in, and what they may do

Objective served: a guide that supports Bernardo and the agents building the app when they decide how people sign in, what each role may do, and how outsiders reach the app. Mode: focused on the priorities. The app may live as a workspace inside a larger app that shares its login and users (undecided), so the guide covers that case and the standalone one.

Findings are marked **Source** (what a cited source says), **Synthesis** (a pattern across sources) or **Inference** (a design consequence drawn from the evidence). Citations give the document and the section as named in the collection; the links to the originals are in the Source key at the end.

## 1. The answer

The evidence is standards, product documentation (GitHub, GitLab, Auth0, WorkOS, Supabase, Laravel), a few practitioner reports and one academic study. It describes patterns and their failure modes. It does not measure them, so the guide gives a decision order with the trade-offs and no ranking.

### 1.1 Decisions to settle first

A synthesis and inference across the views below, not any source's own list.

1. **Authorization around workspace membership and role.** One identity can hold different memberships and rights in different workspaces. For a small internal team with stable job-function differences, RBAC scoped to each workspace is the best-supported starting point. Add ABAC conditions for rules that depend on the record, person or context; consider ReBAC only if sharing and inherited relationships become the main shape of access. These are qualitative choices by policy shape, not measured rankings. (Apache Casbin, "RBAC vs ABAC vs ACL vs ReBAC"; GitHub Docs, "Repository roles for an organization"; GitLab Docs, "Roles and permissions".)
2. **Keep identity, workspace membership and historical actor records distinct.** Removing membership ends access to one workspace; deactivating or blocking the identity stops sign-in across the app; an immutable actor reference is kept for history, and whether contribution content is retained is decided separately. Supported by GitLab and GitHub lifecycle behavior; the app's schema is a design inference. (GitLab Docs, "Delete users" and "Audit events"; GitHub Docs, "Removing a member from your organization" and "Reviewing the audit log for your organization".)
3. **The session boundary.** For shared devices and prompt central revocation, server-side session records, or a hybrid with centrally checked revocation state, give control. Self-contained tokens avoid a per-session lookup but stay usable until expiry unless revocation state is added. Use server-enforced inactivity and overall limits, and do not treat browser-close expiry or SSO as the logout policy. If the workspace lives in a host app, decide whether it shares the host's session boundary or has its own. (NIST SP 800-63B-4, §5.2 "Reauthentication"; OWASP ASVS 5.0, "V7 Session Management"; OWASP JWT Cheat Sheet, "JWTs for user sessions".)
4. **For an outsider: one designated action, or a reusable identity.** A narrowly scoped capability link fits a one-off acceptance without enrollment, but does not identify the human or give membership. An email-authenticated account fits continuing access and person-linked history. A temporary anonymous identity supports multi-step guest continuity but is not durable or verified. Hardening the links belongs to Security and privacy. (Laravel, "Signed URLs"; Supabase, "Anonymous users" and "Passwordless email"; W3C TAG, "Good Practices for Capability URLs".)

### 1.2 Authentication, authorization and policy shape

- **Source.** Authentication verifies identity; authorization checks whether that entity may do the action. A valid sign-in does not imply access to every workspace, object or action. (OWASP Authorization Cheat Sheet, "Introduction"; RFC 6749 §1.4; OpenID Connect Core §§1–2.)
- **Synthesis: one identity, different workspace rights.** GitHub separates organization membership from repository roles and base permissions; GitLab allows different group and project roles and inherited access; WorkOS and Auth0 document per-organization membership and role under one person. The app should resolve the active workspace and authorize against that workspace's membership on each operation; SSO alone does not grant workspace access. (GitHub Docs, "Repository roles for an organization", "Setting base permissions for an organization"; GitLab Docs, "Roles and permissions"; WorkOS, "Users and Organizations", "AuthKit Sessions"; Auth0 Support, "Organization roles in authorization".)

| Model | Fits | Failure mode |
| --- | --- | --- |
| RBAC | Stable team roles mapped to job functions; easy to inspect and audit; scopes per workspace. | Expressing record ownership or contextual exceptions with roles produces too many narrow roles. |
| ABAC | Rules on attributes of person, resource, action and context (an owner edits; colleagues in the same department read). | "Who can read this?" is harder to answer without evaluating attributes, and the attributes must be available at authorization time. |
| ReBAC | Sharing and inheritance through relationships (folders, projects, organizations). | Relationship records must be maintained as objects are created and shared; adds machinery to a small flat system. |

Sources for the table: Apache Casbin, "RBAC vs ABAC vs ACL vs ReBAC"; NIST SP 800-162 (ABAC definition); Google, "Zanzibar" (Abstract, Introduction); OpenFGA, "Model any authorization system". None gives measured maintenance or latency costs for a small app, and Zanzibar's performance figures are for Google's scale.

- **Counterweight.** A peer-reviewed study of 25 database-backed apps found confirmed object-authorization flaws (a check on delete but not on update; project membership checked without the parent-folder relationship). It supports checking the specific object, action and relationship, not only a broad role. It is a selected sample, not a prevalence estimate. (Huang et al., ACM CCS 2024, pp. 1–2 and 11–12; OWASP API Security Top 10, "API1:2019 Broken Object Level Authorization".)
- **Inference.** Second-role approval is an authorization distinction, not an identity method; the approval flow itself belongs to Business logic. (GitHub Docs, "Repository roles for an organization", role action table.)

### 1.3 Workspace access, overlapping grants and user lifecycle

- **Synthesis: make effective access inspectable.** Hierarchical membership can make the source of a user's effective permission hard to see. GitLab documents inherited roles and a "Minimal Access" exception, and GitLab issue #497370 reports wrong membership-source attribution across several inheritance paths; GitHub community reports (#206500, #23660) describe confusion over overlapping team grants. Prefer a simple workspace-scoped role model while the app is small, and show administrators the effective role and its source if inheritance or overlapping grants appear. The second half is an inference from reported usability failures.
- **Source: removing a role does not remove every credential.** GitHub warns that an independently distributed deploy key can keep repository access after a member is removed, so membership changes and other credentials or integrations need separate lifecycle handling. (GitHub Docs, "Repository roles for an organization".)
- **Synthesis: stop access without erasing identity history.** GitLab distinguishes blocking and deactivation from deletion, and deletion that keeps associated records from deletion of contributions; GitHub removal revokes membership while keeping the membership data for a limited restoration period. Identity status, membership, contribution content and event history are separate things. (GitLab Docs, "Delete users"; GitHub Docs, "Removing a member from your organization".)
- **Inference: keep stable actor attribution.** Record an immutable actor ID and, if an identity must be removed, a tombstone or archive mapping; do not rely on mutable email or display name as the only historical key. Record actor, target, action, scope and time separately from current membership. (GitHub Docs, "Audit log events for your organization"; GitLab Docs, "Audit event schema and examples".)
- **Counterweight.** Retention is product-specific: GitHub organization logs cover a documented 180 days; GitLab says audit events are kept indefinitely, but scope and availability depend on tier and role; a GitLab issue (#375576) reports deletion history that was hard to reconstruct. None defines the app's retention. (GitHub Docs, "Reviewing the audit log for your organization"; GitLab Docs, "Audit events".)

### 1.4 Sessions, shared devices and host-app SSO

- **Source.** Session lifetime is independent of login method; a shared device left signed in remains usable as that person. (OWASP Session Management Cheat Sheet.)
- **Synthesis: combine inactivity and overall expiry.** An inactivity limit alone lets an active session run indefinitely; an overall limit alone leaves an idle session usable until the cap. NIST describes terminating on either, with activity resetting only inactivity, and does not prescribe a timeout value, which depends on endpoint, environment, device management and assurance. (NIST SP 800-63B-4, §5.2.)
- **Synthesis: browser-close expiry is a weak boundary.** Old Django community reports show friction combining browser-close with idle expiry and browsers restoring a session after closure; the reports conflict on details and are not a current specification. (Stack Overflow, "Django session expires at browser close OR after time"; "How to expire session due to inactivity in Django?".)
- **Synthesis: central revocation favours server-side state.** A server-side record can be invalidated centrally at the cost of storing and checking it. A self-contained JWT verifies without a record but stays usable until expiry unless a denylist, rotation or other status mechanism is added, which gives back some of the stateless benefit. OWASP ASVS separates backend invalidation for stateful sessions from added revocation for self-contained tokens. (OWASP ASVS 5.0, "V7"; OWASP JWT Cheat Sheet; Rails Security Guide; MACM, "JWT vs server sessions", lines 39–63.)
- **Divergence: no universal JWT versus session winner.** MACM, a practitioner, says conventional browser apps often favour cookie sessions and multi-client APIs may favour JWTs. OWASP says consider plain sessions when revocation state defeats the stateless benefit, and ASVS asks for analysis, not a pattern. (MACM, lines 58–70; OWASP JWT Cheat Sheet, lines 273–278.)
- **Synthesis: SSO shares authentication, not necessarily the app session.** NIST says the app and the identity provider manage sessions separately, and the app's expiry may be followed by silent reauthentication from a still-active IdP session. Auth0 support guidance likewise separates IdP, local and upstream sessions, and an app logout may not clear another app's session. For a hosted workspace, decide whether it shares the host's session boundary, define logout behavior, and enforce app-side expiry either way. (NIST SP 800-63B-4, §5.2; Auth0 Support, "User is Not Logged Out after Password Reset", "Logout Across Multiple Subdomains with auth0-spa-js".)
- **Synthesis: switching workspace keeps the sign-in.** Auth0 and WorkOS document a person with several memberships choosing an active organization; WorkOS tokens may carry the organization ID and that membership's role and permissions. Resolve authorization against the current workspace, recheck after a switch or role change, and do not treat a valid identity session as authorization for the previous workspace. These are provider mechanics; account switching on shared office devices has little direct evidence. (Auth0 Support, "Switch Logged In User Organization Using an Organization Picker"; WorkOS, "AuthKit Sessions".)
- **Counterweight.** Auth.js reports (stale session rows after clearing cookies, revocation friction), a Django Forum report of a second-tab request failing after logout, and Stack Overflow expiry discussions. Implementation reports, not failure rates; they show concurrent requests, multi-tab behavior, cleanup and recovery after expiry need explicit handling. (Auth.js GitHub issues and discussions; Django Forum, "Request with invalid session after concurrent logout or session timeout is considered a BadRequest".)

### 1.5 Account-free access for outsiders

- **Synthesis: a capability link fits one designated response.** A signed route or emailed action link can allow one response without an account. Flero and Workzone document external approvals by link; W3C describes capability URLs as reducing login friction for infrequent collaborators. The link grants authority by possession; it does not establish who used it or create membership, and if person-level attribution matters you need an identity step or an account. (Laravel, "Signed URLs"; Flero, "Public approval links", lines 209–245, 268–293; Workzone, "File Markup and Approval for External Collaborators", lines 4–28; W3C TAG, "Good Practices for Capability URLs", §§1, 3.1, 4, 5.1–5.2.)
- **Synthesis: lower friction for weaker identity and revocation.** Flero documents optional email checks, single-use scope, expiry and cancellation-based revocation; Workzone documents a unique link and retained contact details but not expiry, revocation or identity verification. W3C says links can leak through history, logs and referrers, possession does not separate the intended recipient from a forwardee, and revocation can be coarse; AWS independently says presigned URLs work for anyone holding them and expiry alone does not make them single-use. (W3C TAG, §§4–5; AWS, "Presigned URL FAQ".)
- **Counterweight.** Dropbox Sign says a recipient who opens a signing request on one device, browser or IP may not be able to finish on another and need a new link; a Dropbox community thread reports a user who understood "edit privileges" as account-free editing while recipients were asked to sign in. Product-specific and anecdotal. (Dropbox Help, "How to sign a document in Dropbox Sign"; Dropbox Community, "Share link with edit privileges".)
- **Synthesis: an email-authenticated account fits continuing access and durable actor identity.** Supabase passwordless email links and codes create a signed-in account session; GitHub's invitation needs an account and a matching verified email. Actions can attach to a person ID, though email possession is not proof of a civil or legal identity, and it adds lifecycle and onboarding. An Auth0 report describes cross-browser magic-link friction. (Supabase, "passwordless email sign-in"; GitHub Docs, "Inviting users to join your organization"; Auth0 Support, "Login Fails When Clicking Magic Link Sent from Passwordless Start Endpoint".)
- **Synthesis: a temporary anonymous identity sits between link and account.** Supabase anonymous sign-in gives a guest a temporary user ID and session for guest records across steps in one browser. It is not a verified identity, may be unrecoverable after session loss unless linked, and the provider describes conflicts and cleanup issues. The `authenticated` database role given to anonymous identities is not proof of a full account. (Supabase, "Anonymous users".)
- **Inference: choose by what must be attributable.** If only the acceptance has to happen, a narrowly scoped link avoids enrollment, and the record should say it was a link action. If history must tie later actions to a person, use an account and workspace membership. A guest session suits only temporary continuity where a verified actor is not needed.

### 1.6 Where sources diverge

1. **Authorization-model cost.** Casbin gives qualitative strengths and weaknesses; Zanzibar reports performance at Google's scale; OpenFGA says its model can express all three without a comparative evaluation. "RBAC first" is an inference for this brief, not a source consensus.
2. **Session behavior.** Standards explain expiry and federation boundaries; framework discussions give narrow, sometimes old or conflicting failure reports with no prevalence or current-version evidence.
3. **Account-free links.** Flero has expiry, single use, optional email verification and revocation by cancellation; Workzone omits these; W3C gives generic trade-offs. Do not assume every link has Flero's controls.
4. **Identity history.** GitLab's "indefinite" audit retention and GitHub's 180-day organization log are different product claims with different scope, access, tiers and search; neither settles a retention policy.

## 2. Weak points and suggested next step

- **Cedar was in the map and was not consulted.** The collection review escalated this gap and the user accepted it without another round. No Cedar comparison is used, which narrows the authorization-model coverage.
- **The model comparison is qualitative.** No source quantifies ABAC or ReBAC maintenance burden or applicable ReBAC overhead.
- **Shared office devices.** Direct evidence about real people switching accounts or workspaces on them is sparse. Explicit account switching, local logout, and whether a host app and an embedded workspace share one session boundary remain implementation decisions.
- **Lifecycle and attribution examples are mostly GitHub and GitLab documentation.** They show useful distinctions but do not guarantee the app's own history keeps identity references, stays searchable or meets a retention period.
- **Account-free evidence is thin:** two product documentation examples and general capability guidance, no independent evaluation of acceptance workflows, no completion rates, and no way to establish who an email recipient is.
- **No source gives a required assurance level or a universal timeout** for this product.

**Suggested next step (the writer's inference from the weak points).** The open questions that block a decision sit mostly outside this area: link hardening and replay defense (Security and privacy), the approval flow and what a second role may approve (Business logic), and retention for actor history (Security and privacy and Data). Inside this area, the narrowest worthwhile objective is the shared-session boundary when a workspace sits inside a host app: what the sources say about a host session versus a workspace-specific one, and about users with several workspaces on one device.

## 3. Not consulted

- **Collection A:** GitLab issue #214741 (opening returned HTTP 429); a Dropbox expired-transfer Reddit thread (surfaced, not opened); no OAuth, OIDC or WebAuthn issue or forum counterweights were opened; no separate relevant GitHub Issues bug report was found.
- **Collection B:** Auth0 Organizations general documentation beyond the selected support pages; the Auth0 multi-organization architecture PDF (search-result view only); linked Auth0 invitation and organization-selection guidance; WorkOS custom-role details; broader searches for account switching and per-user "log out all devices" reports; the Auth0 single-logout article (loading or error shell); broader Auth0, Clerk and WorkOS session expiry and revocation documentation; a Stack & Skill JWT-versus-session comparison that failed to open.
- **Collection C:** GitLab issues #39139 and #298723; OWASP Web Security Testing Guide "Weak Password Reset"; additional JWT and session search results.
- **Cedar** authorization documentation, named in the map and not consulted (see section 2).

## 4. Annex: collected, not needed for the main views

- **Authentication method detail:** OWASP's embedded, IdP-mediated and proxy-mediated authentication patterns; WebAuthn and passkey scope; NIST phishing resistance and channel binding. The brief's main decision is the access model, not an assurance level.
- **Protocol distinctions:** OAuth access tokens carry scoped API authorization; OpenID Connect adds identity claims in ID tokens (RFC 6749 §§1.4–1.5; OpenID Connect Core §§1–2). Supports the federation discussion; does not decide local session sharing or permission synchronization.
- **Provider and framework particulars:** Auth.js role and session configuration, Django groups and inactive-user behavior, Laravel logout, other-device invalidation and signed URLs, Rails sessions, Supabase custom claims and RLS, Clerk organization roles, WorkOS membership and session operations, Auth0 organization flows. Examples, not a vendor choice.
- **Other collected evidence:** Dropbox file requests (account-free uploads); GitHub invitations as account-required onboarding; GitLab and GitHub event APIs, role precedence and audit-ingestion permissions.
- **Outside focus:** general threat modeling and detailed email-link hardening belong to Security and privacy; approval workflow mechanics to Business logic.

## Source key

The sources the collectors opened, with their links, so each citation above can be matched by title. Several entries share one origin and count once.

- [Authentication Patterns Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Patterns_Cheat_Sheet.html)
- [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [NIST SP 800-63B-4, Authentication and Authenticator Management](https://pages.nist.gov/800-63-4/sp800-63b.html?locale=en)
- [RFC 6749, OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/info/rfc6749/)
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0-18.html)
- [Web Authentication: An API for accessing Public Key Credentials, Level 3](https://www.w3.org/TR/webauthn-3/)
- [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [Zanzibar: Google’s Consistent, Global Authorization System](https://zanzibar.tech/)
- [OpenFGA](https://openfga.dev/)
- [RBAC vs ABAC vs ACL vs ReBAC: Choosing an Access Control Model](https://casbin.apache.org/docs/access-control-models/)
- [Delete users](https://docs.gitlab.com/user/profile/account/delete_account/)
- [Removing a member from your organization](https://github.com/github/docs/blob/main/content/organizations/managing-membership-in-your-organization/removing-a-member-from-your-organization.md)
- [GitHub organization audit log](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization)
- [Audit events](https://docs.gitlab.com/user/compliance/audit_events/)
- [Members of a project](https://docs.gitlab.com/user/project/members/)
- [Repository roles for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization)
- [Setting base permissions for an organization](https://github.com/github/docs/blob/main/content/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/setting-base-permissions-for-an-organization.md)
- [Roles and permissions](https://docs.gitlab.com/user/permissions/)
- [Make inherited group permissions visible like user permissions in subgroups and projects (#214741)](https://gitlab.com/gitlab-org/gitlab/-/issues/214741)
- [Incorrect membership source attribution when users have multiple inheritance paths (#497370)](https://gitlab.com/gitlab-org/gitlab/-/issues/497370)
- [I am in multiple teams in one org, each with different levels of access to the same repository. What level of access do I end up with?](https://github.com/orgs/community/discussions/206500)
- [Overriding parent team repository access](https://github.com/orgs/community/discussions/23660)
- [Inherit repo permissions by default?](https://github.com/orgs/community/discussions/30945)
- [How to sign a document in Dropbox Sign](https://help.dropbox.com/share/signing-a-dropbox-sign-document)
- [Dropbox Sign invalid-link help](https://help.dropbox.com/share/signature-request-link-invalid)
- [How to create and manage Dropbox file requests](https://help.dropbox.com/share/create-file-request)
- [How can I have someone send me files?](https://community.dropbox.com/en/discussion/820422/how-can-i-have-someone-send-me-files)
- [Share link with edit privileges](https://www.reddit.com/r/dropbox/comments/1ngtgkh/share_link_with_edit_privileges/)
- [Inviting users to join your organization](https://docs.github.com/en/organizations/managing-membership-in-your-organization/inviting-users-to-join-your-organization)
- [Laravel 12 URL generation documentation](https://laravel.com/docs/12.x/urls#signed-urls)
- [Supabase Anonymous Sign-Ins](https://supabase.com/docs/guides/auth/auth-anonymous)
- [Supabase Users](https://supabase.com/docs/guides/auth/users)
- [Supabase passwordless email sign-in](https://supabase.com/docs/guides/auth/auth-email-passwordless)
- [Auth0 Support: Login Fails When Clicking Magic Link Sent from Passwordless Start Endpoint](https://support.auth0.com/center/s/article/passwordless-magic-link-error-The-link-must-be-opened-on-the-same-device-and-browser-from-which-you-submitted-your-email-address)
- [Auth.js Core reference](https://authjs.dev/reference/core)
- [Auth.js RBAC guide](https://authjs.dev/guides/role-based-access-control)
- [Django 3.2 authentication guide](https://docs.djangoproject.com/en/3.2/topics/auth/default/)
- [Django auth reference](https://docs.djangoproject.com/en/5.2/ref/contrib/auth/)
- [Laravel 12 authentication documentation](https://laravel.com/docs/12.x/authentication)
- [Rails Security Guide](https://guides.rubyonrails.org/security.html)
- [Supabase Custom Claims & RBAC guide](https://supabase.com/docs/guides/api/custom-claims-and-role-based-access-control-rbac)
- [WorkOS Users and Organizations](https://workos.com/docs/authkit/users-organizations)
- [Clerk Roles and Permissions](https://clerk.com/docs/guides/organizations/control-access/roles-and-permissions)
- [Auth0 Support: Automatically Adding a User to Multiple Organizations](https://support.auth0.com/center/s/article/Automatically-adding-a-user-to-multiple-Organizations)
- [Auth0 Support: Enable RBAC for user roles in Organizations](https://support.auth0.com/center/s/article/How-to-enable-RBAC-for-use-roles-in-organizations)
- [Auth0 Support: Single Connection Mapped to Multiple Organizations](https://support.auth0.com/center/s/article/Can-a-single-connection-be-mapped-to-multiple-organizations)
- [Auth.js issue #7759](https://github.com/nextauthjs/next-auth/issues/7759)
- [Auth.js discussion #4394](https://github.com/nextauthjs/next-auth/discussions/4394)
- [Auth.js discussion #5334](https://github.com/nextauthjs/next-auth/discussions/5334)
- [Django Forum: Request with invalid session after concurrent logout or session timeout is considered a BadRequest](https://forum.djangoproject.com/t/request-with-invalid-session-after-concurrent-logout-or-session-timeout-is-considered-a-badrequest/20980)
- [Django session expires at browser close OR after time](https://stackoverflow.com/questions/14146396/django-session-expires-at-browser-close-or-after-time)
- [How to expire session due to inactivity in Django?](https://stackoverflow.com/questions/3024153/how-to-expire-session-due-to-inactivity-in-django)
- [Auth0 Support: User is Not Logged Out after Password Reset](https://support.auth0.com/center/s/article/Users-Do-Not-Appear-to-be-Logged-Out-After-Password-Reset)
- [Invalidating an Access Token after User Logout](https://support.auth0.com/center/s/article/Invalidate-the-API-token-after-user-logout)
- [Switch Logged In User Organization Using an Organization Picker](https://support.auth0.com/center/s/article/switch-logged-in-user-organization-using-an-organization-picker)
- [SSO is Not Working with Organization Feature](https://support.auth0.com/center/s/article/SSO-is-not-working-with-Organizations)
- [WorkOS AuthKit Sessions](https://workos.com/docs/authkit/sessions)
- [WorkOS Session API reference](https://workos.com/docs/reference/authkit/session)
- [Auth0 Support: Logout Across Multiple Subdomains with auth0-spa-js](https://support.auth0.com/center/s/article/Logout-across-multiple-subdomains-with-auth0-spa-js)
- [Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- [Public approval links](https://docs.flero.ai/08-approvals/public-approval-links/)
- [File Markup and Approval for External Collaborators](https://helpdocs.workzone.com/article/578-external-file-markup-and-approval)
- [Good Practices for Capability URLs](https://www.w3.org/TR/capability-urls/)
- [FAQ](https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/faq.html)
- [OAuth2 Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html)
- [JWT vs server sessions: which one for your app (and why)](https://miguelacm.es/en/blog/jwt-vs-sesiones-cookies)
- [JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html)
- [V7 Session Management](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x16-V7-Session-Management.md)
- [Detecting Broken Object-Level Authorization Vulnerabilities in Database-Backed Applications](https://leehaofeng.github.io/papers/2024-BolaRay.pdf)
- [API1:2019 Broken Object Level Authorization](https://github.com/OWASP/API-Security/blob/master/editions/2019/en/0xa1-broken-object-level-authorization.md)
- [Audit log events for your organization](https://docs.github.com/en/enterprise-cloud@latest/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/audit-log-events-for-your-organization)
- [Audit events API](https://docs.gitlab.com/api/audit_events/)
- [Audit event schema and examples](https://docs.gitlab.com/user/compliance/audit_event_schema/)
- [Audit Events — Log initial trigger of project and group deletions (#375576)](https://gitlab.com/gitlab-org/gitlab/-/work_items/375576)
- [Audit Log Required Permissions](https://github.com/orgs/community/discussions/11746)
- [Webhook event for member_updated](https://github.com/orgs/community/discussions/144911)
- [GitLab issue #39139: Display project deletion in group audit event log](https://gitlab.com/gitlab-org/gitlab/-/issues/39139)
- [GitLab issue #298723: null authors in audit events](https://gitlab.com/gitlab-org/gitlab/-/issues/298723)
- [OWASP Web Security Testing Guide: weak password reset](https://wstg.org/latest/4-Web_Application_Security_Testing/04-Authentication/09-Weak_Password_Change_or_Reset_Functionalities/)
- [JWT vs. Sessions: Choosing an Authentication Strategy for Your API](https://www.stackandskill.com/blog/jwt-vs-session-authentication)

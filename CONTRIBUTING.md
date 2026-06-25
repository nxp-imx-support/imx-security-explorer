# Contributing to i.MX Security Explorer

## Submitting Changes via Patch Files

If you've made changes using the Admin tool, you can generate a patch file and submit it to the maintainers for review.

### Prerequisites

- **Git** installed ([Download Git](https://git-scm.com/downloads))

### Step-by-step Instructions

After running `generate_patch.sh`, review `patches/SUBMISSION_INSTRUCTIONS.txt` file for step-by-step instructions.

---

## Usage Example

### User Workflow

```bash
./run_admin.sh
```

*(Make changes in GUI)*

```bash
./generate_patch.sh
```

**Output:**
```
✓ Patch file created: patches/data-changes-20240115-143022.patch
✓ Submission instructions saved: patches/SUBMISSION_INSTRUCTIONS.txt
```

---

## Need Help?

Visit the [repository issues page](https://github.com/nxp-imx-support/imx-security-explorer/issues) for support.

